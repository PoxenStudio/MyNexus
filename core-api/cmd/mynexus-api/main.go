package main

import (
	"fmt"
	"log"

	"mynexus/core-api/internal/api"
	"mynexus/core-api/internal/config"
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

	router := api.NewRouter(cfg, store)

	log.Printf("core-api listening on :%s (storage=%s)", cfg.Server.Port, cfg.Storage.Database)
	if err := router.Run(":" + cfg.Server.Port); err != nil {
		log.Fatal(err)
	}
}
