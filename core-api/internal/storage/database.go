package storage

import "database/sql"

// Database is the abstraction all storage backends (sqlite, postgres) implement,
// so the rest of Core API never depends on a concrete driver. Both backends run
// the same service-layer SQL (see storage/postgres's placeholder-rewriting driver),
// so DB() can be handed to services unchanged regardless of backend.
type Database interface {
	DB() *sql.DB
	Health() error
	Close() error
}
