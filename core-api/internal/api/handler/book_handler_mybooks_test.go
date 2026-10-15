package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
	"mynexus/core-api/internal/storage/sqlite"
)

func TestAnalysisByMyBooksIDReturnsCompletedAfterSummarize(t *testing.T) {
	gin.SetMode(gin.TestMode)
	store, err := sqlite.Open(filepath.Join(t.TempDir(), "mynexus.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()

	books := service.NewBookService(store.DB(), t.TempDir())
	tasks := service.NewTaskService(store.DB())
	book, ingest, _, err := books.CreateBookWithMyBooksID("local-user", "epub", models.SourceOriginMyBooks, 123)
	if err != nil {
		t.Fatal(err)
	}
	if err := books.SetStatus(book.ID, models.BookStatusReady); err != nil {
		t.Fatal(err)
	}
	if err := tasks.Complete(ingest.ID); err != nil {
		t.Fatal(err)
	}
	summarize, err := tasks.CreateTask(book.ID, "local-user", models.TaskTypeSummarize)
	if err != nil {
		t.Fatal(err)
	}
	if err := tasks.Complete(summarize.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := store.DB().Exec(`UPDATE books SET reading_guide = ? WHERE id = ?`, "Guide", book.ID); err != nil {
		t.Fatal(err)
	}

	router := gin.New()
	router.GET("/api/v1/books/by-mybooks-id/:mybooks_id", (&BookHandler{books: books, tasks: tasks}).AnalysisByMyBooksID)
	req := httptest.NewRequest(http.MethodGet, "/api/v1/books/by-mybooks-id/123", nil)
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, req)
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d: %s", recorder.Code, recorder.Body.String())
	}

	var response dto.MyBooksAnalysisResponse
	if err := json.Unmarshal(recorder.Body.Bytes(), &response); err != nil {
		t.Fatal(err)
	}
	if response.AnalysisStatus != models.TaskStatusCompleted || response.ReadingGuide != "Guide" {
		t.Fatalf("response = %+v, want completed status and guide", response)
	}
	if response.IngestTask == nil || response.SummarizeTask == nil {
		t.Fatalf("response omitted task states: %+v", response)
	}
}

func TestAnalysisByMyBooksIDReportsMissingBookAndEmptyIngest(t *testing.T) {
	gin.SetMode(gin.TestMode)
	store, err := sqlite.Open(filepath.Join(t.TempDir(), "mynexus.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()

	books := service.NewBookService(store.DB(), t.TempDir())
	tasks := service.NewTaskService(store.DB())
	book, ingest, _, err := books.CreateBookWithMyBooksID("local-user", "epub", models.SourceOriginMyBooks, 456)
	if err != nil {
		t.Fatal(err)
	}
	if err := books.SetStatus(book.ID, models.BookStatusReady); err != nil {
		t.Fatal(err)
	}
	if err := tasks.Complete(ingest.ID); err != nil {
		t.Fatal(err)
	}

	router := gin.New()
	router.GET("/api/v1/books/by-mybooks-id/:mybooks_id", (&BookHandler{books: books, tasks: tasks}).AnalysisByMyBooksID)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/books/by-mybooks-id/456", nil)
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, req)
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d: %s", recorder.Code, recorder.Body.String())
	}
	var response dto.MyBooksAnalysisResponse
	if err := json.Unmarshal(recorder.Body.Bytes(), &response); err != nil {
		t.Fatal(err)
	}
	if response.AnalysisStatus != models.TaskStatusFailed || response.ErrorMsg == "" {
		t.Fatalf("response = %+v, want failed analysis with reason", response)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/v1/books/by-mybooks-id/999", nil)
	recorder = httptest.NewRecorder()
	router.ServeHTTP(recorder, req)
	if recorder.Code != http.StatusNotFound {
		t.Fatalf("missing book status = %d, want 404", recorder.Code)
	}
}
