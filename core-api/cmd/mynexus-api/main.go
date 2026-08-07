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
	"mynexus/core-api/internal/dispatch"
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
// state, not a network call of its own). Also doubles as the periodic
// safety-net interval for dispatcher.TryDispatch (see watchWorkerHealth) —
// one ticker, two jobs, since both only matter on roughly the same
// timescale.
const workerHealthCheckInterval = 20 * time.Second

// recoverOrphanedTasks handles every task left stuck pending/processing —
// see TaskService.RequeueOrphanedIngest/FailOrphanedSummarize for why
// ingest and summarize are treated differently here. Ingest tasks are
// requeued and immediately offered to dispatcher.TryDispatch so they
// resume with no user action needed; summarize tasks (not
// dispatcher-managed — see internal/dispatch's package doc comment) fall
// back to the older "mark failed, surface it on the Tasks admin page"
// behavior.
func recoverOrphanedTasks(tasks *service.TaskService, books *service.BookService, dispatcher *dispatch.Dispatcher, reason string) {
	requeued, err := tasks.RequeueOrphanedIngest()
	if err != nil {
		log.Printf("recover orphaned tasks: requeue ingest: %v", err)
	}
	for _, t := range requeued {
		// It was "processing" (or still "pending", either way presumed
		// mid-run); nothing is actually running on it right now, so
		// "pending"/queued is the accurate book status until the
		// dispatcher below actually resumes it.
		if err := books.SetStatus(t.BookID, models.BookStatusPending); err != nil {
			log.Printf("recover orphaned tasks: set book %s pending: %v", t.BookID, err)
		}
	}
	if len(requeued) > 0 {
		log.Printf("requeued %d orphaned ingest task(s): %s", len(requeued), reason)
		dispatcher.TryDispatch()
	}

	failed, err := tasks.FailOrphanedSummarize(reason)
	if err != nil {
		log.Printf("recover orphaned tasks: fail summarize: %v", err)
	}
	if len(failed) > 0 {
		log.Printf("failed %d orphaned summarize task(s): %s", len(failed), reason)
	}
}

// watchWorkerHealth polls the shared Worker gRPC channel's connectivity
// state. Runs until ctx is canceled, and does one of two things every tick:
//
//   - Worker confirmed unreachable: recover any task left stuck
//     pending/processing — Worker tracks an in-flight task only in its own
//     process memory (see docs/系统设计文档.md §3.x "Worker 只算"), so once
//     it's gone, nothing will ever call back
//     ReportProgress/ReportComplete/ReportFail for whatever it was running.
//   - Otherwise: nudge the dispatcher anyway, as a safety net in case a
//     queued ingest task was somehow never picked up by one of the
//     triggered dispatch points (task creation, task completion/failure) —
//     cheap (a no-op unless something really is queued) and makes the
//     whole queue self-healing on a ~20s cadence no matter what.
//
// TransientFailure covers both "Worker's process is actually gone" and "a
// single keepalive ping got dropped and a reconnect is in flight" — a task
// caught by the latter gets requeued even though Worker comes back moments
// later, which just means it's dispatched again a few seconds after it
// would have been anyway. Re-running an ingest task from scratch is safe
// (see RequeueOrphanedIngest's doc comment), so this false-positive is
// harmless, unlike the old fail-and-require-manual-retry behavior.
func watchWorkerHealth(ctx context.Context, worker *coordinator.WorkerClient, tasks *service.TaskService, books *service.BookService, dispatcher *dispatch.Dispatcher) {
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
				recoverOrphanedTasks(tasks, books, dispatcher, "Worker 服务不可达，任务已中断")
			default:
				dispatcher.TryDispatch()
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
	// api.NewRouter's internals out through this function. The Dispatcher
	// below is the one exception — it must be a true singleton (its
	// in-process mutex only actually serializes concurrent dispatch
	// attempts if every caller shares the same instance — see
	// internal/dispatch.Dispatcher) — so it's built once here and threaded
	// through to both the gRPC server and the HTTP router, unlike
	// bookSvc/taskSvc.
	db := store.DB()
	bookSvc := service.NewBookService(db, cfg.Storage.UploadDir)
	taskSvc := service.NewTaskService(db)

	workerClient := coordinator.NewWorkerClient(cfg.Worker.URL)
	defer workerClient.Close()

	dispatcher := dispatch.New(taskSvc, bookSvc, workerClient, cfg.Worker.MaxConcurrentTasks)

	// Bind the gRPC port *before* anything that might dispatch to Worker —
	// TriggerIngest's handler calls back into this port to report progress
	// almost immediately (see worker/src/server.py), so if recovery below
	// re-dispatches a requeued task while this port is still unbound,
	// Worker's very first callback fails with UNAVAILABLE and the task is
	// left dispatched but silently stuck (Worker doesn't retry that
	// callback on its own). Actually starting the accept loop (Serve) can
	// still happen in the background afterwards — a listener that's bound
	// but not yet Accept()-ing still queues incoming connections at the OS
	// level, so this alone is enough to close the race.
	grpcSrv := grpcserver.New(cfg, service.NewBookService(db, cfg.Storage.UploadDir), taskSvc, workerClient, dispatcher)
	grpcLis, err := grpcSrv.Listen()
	if err != nil {
		log.Fatalf("grpc server failed: %v", err)
	}

	// Any task still pending/processing predates this process — whatever was
	// tracking it (this process's or, for a task Worker was mid-run on,
	// Worker's own in-memory state) is gone. Requeue-and-redispatch (ingest)
	// or fail-for-manual-retry (summarize) rather than leaving it stuck
	// forever with no automatic recovery. See recoverOrphanedTasks and
	// docs/Todos.md.
	recoverOrphanedTasks(taskSvc, bookSvc, dispatcher, "服务重启导致任务中断")

	healthCtx, cancelHealth := context.WithCancel(context.Background())
	defer cancelHealth()
	go watchWorkerHealth(healthCtx, workerClient, taskSvc, bookSvc, dispatcher)

	go func() {
		log.Printf("core-api grpc listening on :%s", cfg.Server.GRPCPort)
		if err := grpcSrv.Serve(grpcLis); err != nil {
			log.Fatalf("grpc server failed: %v", err)
		}
	}()

	router := api.NewRouter(cfg, store, workerClient, dispatcher)

	log.Printf("core-api listening on :%s (storage=%s)", cfg.Server.Port, cfg.Storage.Database)
	if err := router.Run(":" + cfg.Server.Port); err != nil {
		log.Fatal(err)
	}
}
