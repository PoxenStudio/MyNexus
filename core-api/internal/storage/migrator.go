package storage

import (
	"database/sql"
	"embed"
	"fmt"
	"sort"
	"strings"
)

// RunMigrations applies migration files under dir (in fsys) that aren't yet
// recorded in the schema_migrations table, in filename order, each inside its
// own transaction. Shared by both the sqlite and postgres backends so the
// upgrade behavior — and the schema-check-on-connect requirement — is
// identical regardless of which database is configured.
//
// Recording applied filenames (rather than re-running every file's full
// contents on every startup, as the original single-file migration did) is
// what makes it safe to ship a future migration with a real ALTER TABLE:
// idempotent "CREATE ... IF NOT EXISTS" statements tolerate re-execution,
// ALTER TABLE ADD COLUMN does not. New schema changes should be added as a
// new numbered file (e.g. 0002_*.sql), not edits to an already-shipped one.
func RunMigrations(db *sql.DB, fsys embed.FS, dir string) error {
	if _, err := db.Exec(`CREATE TABLE IF NOT EXISTS schema_migrations (
		name       TEXT PRIMARY KEY,
		applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	)`); err != nil {
		return fmt.Errorf("create schema_migrations table: %w", err)
	}

	entries, err := fsys.ReadDir(dir)
	if err != nil {
		return fmt.Errorf("read migrations dir: %w", err)
	}
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		if !e.IsDir() {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)

	for _, name := range names {
		applied, err := isApplied(db, name)
		if err != nil {
			return fmt.Errorf("check migration %s: %w", name, err)
		}
		if applied {
			continue
		}

		script, err := fsys.ReadFile(dir + "/" + name)
		if err != nil {
			return fmt.Errorf("read migration %s: %w", name, err)
		}

		if err := applyMigration(db, name, string(script)); err != nil {
			return err
		}
	}
	return nil
}

func isApplied(db *sql.DB, name string) (bool, error) {
	var exists int
	err := db.QueryRow(`SELECT 1 FROM schema_migrations WHERE name = ?`, name).Scan(&exists)
	switch err {
	case nil:
		return true, nil
	case sql.ErrNoRows:
		return false, nil
	default:
		return false, err
	}
}

func applyMigration(db *sql.DB, name, script string) error {
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("begin migration %s: %w", name, err)
	}
	defer tx.Rollback() //nolint:errcheck // no-op once committed

	// Split on ";" so this works against Postgres too: pgx's extended query
	// protocol (used by *sql.DB's prepared-statement path) rejects multiple
	// statements in a single Exec, unlike SQLite's driver.
	for _, stmt := range splitStatements(script) {
		if _, err := tx.Exec(stmt); err != nil {
			return fmt.Errorf("apply migration %s: %w", name, err)
		}
	}
	if _, err := tx.Exec(`INSERT INTO schema_migrations (name) VALUES (?)`, name); err != nil {
		return fmt.Errorf("record migration %s: %w", name, err)
	}
	return tx.Commit()
}

func splitStatements(script string) []string {
	parts := strings.Split(script, ";")
	stmts := make([]string, 0, len(parts))
	for _, p := range parts {
		if s := strings.TrimSpace(p); s != "" {
			stmts = append(stmts, s)
		}
	}
	return stmts
}
