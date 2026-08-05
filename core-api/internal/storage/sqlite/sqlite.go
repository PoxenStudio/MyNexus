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

	// WAL mode lets readers and the single writer proceed concurrently instead
	// of taking a whole-file lock on every write; busy_timeout makes SQLite
	// retry for a bit instead of returning SQLITE_BUSY immediately when a
	// writer collides with another in-flight write (see core-api <-> worker
	// gRPC calls landing at the same time).
	dsn := path + "?_pragma=journal_mode(WAL)&_pragma=busy_timeout(5000)"
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}
	// SQLite allows only one writer at a time regardless of pool size; capping
	// at 1 connection serializes writes through database/sql instead of
	// letting them race and hit SQLITE_BUSY.
	db.SetMaxOpenConns(1)
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
