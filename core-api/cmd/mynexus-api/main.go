package main

import (
	"fmt"
	"log"

	"mynexus/core-api/internal/api"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/grpcserver"
	"mynexus/core-api/internal/service"
	"mynexus/core-api/internal/storage"
	"mynexus/core-api/internal/storage/postgres"
	"mynexus/core-api/internal/storage/sqlite"
)

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

	if err := service.NewAdminUserService(store.DB()).EnsureDefaultAdmin(); err != nil {
		log.Fatalf("failed to seed default admin account: %v", err)
	}

	// The gRPC server (Worker-facing: progress/complete/fail/keyword-search —
	// see .claude/memory/mynexus_grpc_migration.md) and the Gin HTTP server
	// (browser-facing) are separate listeners sharing the same *sql.DB;
	// BookService/TaskService are stateless wrappers around it, so
	// constructing a second instance for gRPC is safe and avoids threading
	// api.NewRouter's internals out through this function.
	db := store.DB()
	grpcSrv := grpcserver.New(cfg, service.NewBookService(db, cfg.Storage.UploadDir), service.NewTaskService(db))
	go func() {
		log.Printf("core-api grpc listening on :%s", cfg.Server.GRPCPort)
		if err := grpcSrv.Serve(); err != nil {
			log.Fatalf("grpc server failed: %v", err)
		}
	}()

	router := api.NewRouter(cfg, store)

	log.Printf("core-api listening on :%s (storage=%s)", cfg.Server.Port, cfg.Storage.Database)
	if err := router.Run(":" + cfg.Server.Port); err != nil {
		log.Fatal(err)
	}
}
