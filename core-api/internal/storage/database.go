package storage

// Database is the abstraction all storage backends (sqlite, postgres, ...) implement,
// so the rest of Core API never depends on a concrete driver.
type Database interface {
	Health() error
	Close() error
}
