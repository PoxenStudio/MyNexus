package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"google.golang.org/grpc/connectivity"

	"mynexus/core-api/internal/api"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/grpcserver"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
	"mynexus/core-api/internal/storage"
	"mynexus/core-api/internal/storage/postgres"
	"mynexus/core-api/internal/storage/sqlite"
)

// workerHealthCheckInterval paces watchWorkerHealth below — frequent enough
// that a dead Worker doesn't leave tasks stuck for long, coarse enough not
// to matter when it hasn't (this is a poll of already-tracked gRPC channel
// state, not a network call of its own).
const workerHealthCheckInterval = 20 * time.Second

// reconcileOrphanedTasks fails every task still pending/processing — see
// service.TaskService.ReconcileOrphaned for why this is safe/necessary — and
// fixes up the book status for any affected ingest task, mirroring
// grpcserver.ReportFail's handling of a Worker-reported failure.
func reconcileOrphanedTasks(tasks *service.TaskService, books *service.BookService, reason string) {
	orphaned, err := tasks.ReconcileOrphaned(reason)
	if err != nil {
		log.Printf("reconcile orphaned tasks: %v", err)
		return
	}
	for _, t := range orphaned {
		if t.Type == models.TaskTypeIngest {
			if err := books.SetStatus(t.BookID, models.BookStatusFailed); err != nil {
				log.Printf("reconcile orphaned tasks: set book %s failed: %v", t.BookID, err)
			}
		}
	}
	if len(orphaned) > 0 {
		log.Printf("reconciled %d orphaned task(s): %s", len(orphaned), reason)
	}
}

// watchWorkerHealth polls the shared Worker gRPC channel's connectivity
// state and, whenever Worker is found unreachable, reconciles any task left
// stuck pending/processing — Worker tracks an in-flight task only in its own
// process memory (see docs/系统设计文档.md §3.x "Worker 只算"), so once it's
// gone, nothing will ever call back ReportProgress/ReportComplete/ReportFail
// for whatever it was running. Runs until ctx is canceled.
//
// TransientFailure covers both "Worker's process is actually gone" and "a
// single keepalive ping got dropped and a reconnect is in flight" — a task
// caught by the latter gets marked failed even though Worker comes back
// moments later. Accepted trade-off: false positives here are cheap (retry
// the task from the Tasks admin page), stuck-forever tasks from a real
// outage are not.
func watchWorkerHealth(ctx context.Context, worker *coordinator.WorkerClient, tasks *service.TaskService, books *service.BookService) {
	ticker := time.NewTicker(workerHealthCheckInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			// Nudges a channel that's never made a real call out of Idle, so
			// ConnState() below reflects an actual attempt rather than "no
			// traffic yet" — see WorkerClient.Connect's doc comment.
			worker.Connect()
			switch worker.ConnState() {
			case connectivity.TransientFailure, connectivity.Shutdown:
				reconcileOrphanedTasks(tasks, books, "Worker 服务不可达，任务已中断，请重试")
			}
		}
	}
}

func openStore(cfg config.Config) (storage.Database, error) {
	switch cfg.Storage.Database {
	case "postgres":
		if cfg.Storage.Postgres.DSN == "" {
			return nil, fmt.Errorf("storage.postgres.dsn is required when storage.database is \"postgres\"")
		}
		return postgres.Open(cfg.Storage.Postgres.DSN)
	case "sqlite", "":
		return sqlite.Open(cfg.Storage.SQLite.Path)
	default:
		return nil, fmt.Errorf("unsupported storage.database %q (want \"sqlite\" or \"postgres\")", cfg.Storage.Database)
	}
}

func main() {
	cfg := config.Load()

	store, err := openStore(cfg)
	if err != nil {
		log.Fatalf("failed to open %s store: %v", cfg.Storage.Database, err)
	}
	defer store.Close()

	if err := service.NewUserService(store.DB()).EnsureDefaultAdmin(); err != nil {
		log.Fatalf("failed to seed default admin account: %v", err)
	}

	// The gRPC server (Worker-facing: progress/complete/fail/keyword-search —
	// see .claude/memory/mynexus_grpc_migration.md) and the Gin HTTP server
	// (browser-facing) are separate listeners sharing the same *sql.DB;
	// BookService/TaskService are stateless wrappers around it, so
	// constructing a second instance for gRPC is safe and avoids threading
	// api.NewRouter's internals out through this function.
	db := store.DB()
	bookSvc := service.NewBookService(db, cfg.Storage.UploadDir)
	taskSvc := service.NewTaskService(db)

	// Any task still pending/processing predates this process — whatever was
	// tracking it (this process's or, for a task Worker was mid-run on,
	// Worker's own in-memory state) is gone, so it would otherwise stay stuck
	// forever with no automatic recovery. See reconcileOrphanedTasks and
	// docs/Todos.md.
	reconcileOrphanedTasks(taskSvc, bookSvc, "服务重启导致任务中断，请重试")

	workerClient := coordinator.NewWorkerClient(cfg.Worker.URL)
	defer workerClient.Close()

	healthCtx, cancelHealth := context.WithCancel(context.Background())
	defer cancelHealth()
	go watchWorkerHealth(healthCtx, workerClient, taskSvc, bookSvc)

	grpcSrv := grpcserver.New(cfg, service.NewBookService(db, cfg.Storage.UploadDir), taskSvc, workerClient)
	go func() {
		log.Printf("core-api grpc listening on :%s", cfg.Server.GRPCPort)
		if err := grpcSrv.Serve(); err != nil {
			log.Fatalf("grpc server failed: %v", err)
		}
	}()

	router := api.NewRouter(cfg, store, workerClient)

	log.Printf("core-api listening on :%s (storage=%s)", cfg.Server.Port, cfg.Storage.Database)
	if err := router.Run(":" + cfg.Server.Port); err != nil {
		log.Fatal(err)
	}
}
