package dto

import (
	"database/sql"
	"testing"

	"mynexus/core-api/internal/models"
)

func TestNewMyBooksAnalysisResponse(t *testing.T) {
	book := models.Book{
		ID: "book-id", Status: models.BookStatusReady,
		MyBooksID: sql.NullInt64{Int64: 123, Valid: true},
	}

	ingest := &models.Task{ID: "ingest-id", Status: models.TaskStatusCompleted}
	response := NewMyBooksAnalysisResponse(book, ingest, nil, true)
	if response.AnalysisStatus != models.TaskStatusProcessing {
		t.Fatalf("analysis status = %q, want processing", response.AnalysisStatus)
	}

	response = NewMyBooksAnalysisResponse(book, ingest, nil, false)
	if response.AnalysisStatus != models.TaskStatusFailed || response.ErrorMsg == "" {
		t.Fatalf("analysis response = %+v, want failed status and reason", response)
	}

	summarize := &models.Task{ID: "summarize-id", Status: models.TaskStatusCompleted}
	response = NewMyBooksAnalysisResponse(book, ingest, summarize, true)
	if response.AnalysisStatus != models.TaskStatusCompleted {
		t.Fatalf("analysis status = %q, want completed", response.AnalysisStatus)
	}

	summarize.Status = models.TaskStatusFailed
	response = NewMyBooksAnalysisResponse(book, ingest, summarize, true)
	if response.AnalysisStatus != models.TaskStatusFailed {
		t.Fatalf("analysis status = %q, want failed", response.AnalysisStatus)
	}

	ingest.Status = models.TaskStatusProcessing
	response = NewMyBooksAnalysisResponse(book, ingest, summarize, true)
	if response.AnalysisStatus != models.TaskStatusProcessing {
		t.Fatalf("analysis status = %q, want processing", response.AnalysisStatus)
	}
}
