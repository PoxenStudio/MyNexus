package main

import (
	"log"

	"mynexus/core-api/internal/api"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/storage/sqlite"
)

func main() {
	cfg := config.Load()

	store, err := sqlite.Open(cfg.Storage.SQLite.Path)
	if err != nil {
		log.Fatalf("failed to open sqlite store: %v", err)
	}
	defer store.Close()

	router := api.NewRouter(cfg, store)

	log.Printf("core-api listening on :%s", cfg.Server.Port)
	if err := router.Run(":" + cfg.Server.Port); err != nil {
		log.Fatal(err)
	}
}
