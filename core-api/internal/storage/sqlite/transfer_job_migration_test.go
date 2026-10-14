package sqlite

import (
	"path/filepath"
	"testing"
)

func TestTransferJobsAreNotDatabaseLockedToOneActiveTask(t *testing.T) {
	store, err := Open(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatalf("open migrated database: %v", err)
	}
	defer store.Close()

	for _, id := range []string{"book-1", "book-2"} {
		if _, err := store.DB().Exec(
			`INSERT INTO books (id, user_id, source_format, file_path) VALUES (?, ?, ?, ?)`,
			id, "user-1", "epub", id+".epub",
		); err != nil {
			t.Fatalf("insert %s: %v", id, err)
		}
	}

	for _, job := range []struct {
		id, bookID, kind, status string
	}{
		{"export-1", "book-1", "export", "processing"},
		{"import-2", "book-2", "import", "pending"},
	} {
		if _, err := store.DB().Exec(
			`INSERT INTO transfer_jobs (id, book_id, type, status, created_at, updated_at)
			 VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)`,
			job.id, job.bookID, job.kind, job.status,
		); err != nil {
			t.Fatalf("insert transfer job %s: %v", job.id, err)
		}
	}
}
