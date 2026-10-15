package service

import (
	"sync"
	"testing"

	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/storage/sqlite"
)

func TestCreateBookWithMyBooksIDIsIdempotentConcurrently(t *testing.T) {
	store, err := sqlite.Open(t.TempDir() + "/mynexus.db")
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()

	books := NewBookService(store.DB(), t.TempDir())
	const workers = 12
	type result struct {
		book *models.Book
		task *models.Task
	}
	results := make(chan result, workers)
	created := make(chan bool, workers)
	errs := make(chan error, workers)
	var wg sync.WaitGroup
	for range workers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			book, task, wasCreated, err := books.CreateBookWithMyBooksID("local-user", "epub", models.SourceOriginDirectUpload, 913)
			if err != nil {
				errs <- err
				return
			}
			results <- result{book: book, task: task}
			created <- wasCreated
		}()
	}
	wg.Wait()
	close(results)
	close(created)
	close(errs)

	for err := range errs {
		t.Fatal(err)
	}
	var bookID string
	createdCount := 0
	var taskID string
	for result := range results {
		book := result.book
		if bookID == "" {
			bookID = book.ID
		}
		if book.ID != bookID {
			t.Fatalf("got different book IDs for same mybooks_id: %s and %s", bookID, book.ID)
		}
		if result.task == nil {
			t.Fatal("missing ingest task")
		}
		if taskID == "" {
			taskID = result.task.ID
		}
		if result.task.ID != taskID {
			t.Fatalf("got different ingest task IDs for same mybooks_id")
		}
	}
	for wasCreated := range created {
		if wasCreated {
			createdCount++
		}
	}
	if createdCount != 1 {
		t.Fatalf("created count = %d, want 1", createdCount)
	}

	var count int
	if err := store.DB().QueryRow(`SELECT COUNT(*) FROM books WHERE mybooks_id = ?`, 913).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatalf("book count = %d, want 1", count)
	}
	if err := store.DB().QueryRow(`SELECT COUNT(*) FROM tasks WHERE book_id = ? AND type = ?`, bookID, models.TaskTypeIngest).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatalf("ingest task count = %d, want 1", count)
	}
}
