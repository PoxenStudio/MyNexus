package sqlite

import (
	"database/sql"
	"embed"
	"fmt"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"

	"mynexus/core-api/internal/storage"
)

//go:embed migrations/*.sql
var migrationFiles embed.FS

// Store is the SQLite-backed implementation of storage.Database.
type Store struct {
	db *sql.DB
}

// Open connects to the SQLite file at path (creating its parent directory if
// needed) and applies any pending migrations found under migrations/.
func Open(path string) (*Store, error) {
	if dir := filepath.Dir(path); dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return nil, fmt.Errorf("create data dir: %w", err)
		}
	}

	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("ping sqlite: %w", err)
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
