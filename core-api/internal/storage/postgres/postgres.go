package postgres

import (
	"database/sql"
	"embed"
	"fmt"

	"mynexus/core-api/internal/storage"
)

//go:embed migrations/*.sql
var migrationFiles embed.FS

// Store is the Postgres-backed implementation of storage.Database.
type Store struct {
	db *sql.DB
}

// Open connects to Postgres via dsn (e.g. "postgres://user:pass@host:5432/mynexus?sslmode=disable")
// and applies any pending migrations found under migrations/.
func Open(dsn string) (*Store, error) {
	db, err := sql.Open(driverName, dsn)
	if err != nil {
		return nil, fmt.Errorf("open postgres: %w", err)
	}
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("ping postgres: %w", err)
	}

	if err := storage.RunMigrations(db, migrationFiles, "migrations"); err != nil {
		return nil, err
	}
	return &Store{db: db}, nil
}

// DB exposes the underlying *sql.DB for service-layer queries.
func (s *Store) DB() *sql.DB {
	return s.db
}

func (s *Store) Health() error {
	return s.db.Ping()
}

func (s *Store) Close() error {
	return s.db.Close()
}
