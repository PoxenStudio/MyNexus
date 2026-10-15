package dto

import (
	"encoding/json"

	"mynexus/core-api/internal/models"
)

type TaskResponse struct {
	ID       string `json:"id"`
	BookID   string `json:"book_id"`
	Type     string `json:"type"`
	Status   string `json:"status"`
	Progress int    `json:"progress"`
	ErrorMsg string `json:"error_msg"`
	// Dispatched is false while an ingest task is queued, waiting for a
	// free worker.max_concurrent_tasks slot (see internal/dispatch.Dispatcher) —
	// true once it's actually been handed to Worker. Always true for a
	// summarize task (not dispatcher-managed — see that package's doc
	// comment) the instant it exists, since those still go straight to
	// Worker. A "pending" task with Dispatched=false is what the frontend
	// should label "queued" rather than a generic "pending".
	Dispatched bool                   `json:"dispatched"`
	StagesLog  []models.StageLogEntry `json:"stages_log"`
	CreatedAt  string                 `json:"created_at"`
	UpdatedAt  string                 `json:"updated_at"`
}

func NewTaskResponse(t models.Task) TaskResponse {
	stagesLog := []models.StageLogEntry{}
	_ = json.Unmarshal([]byte(t.StagesLog), &stagesLog)
	return TaskResponse{
		ID: t.ID, BookID: t.BookID, Type: t.Type, Status: t.Status, Progress: t.Progress,
		ErrorMsg: t.ErrorMsg, Dispatched: t.Type != models.TaskTypeIngest || t.DispatchedAt != "",
		StagesLog: stagesLog, CreatedAt: t.CreatedAt, UpdatedAt: t.UpdatedAt,
	}
}

type TaskListResponse struct {
	Items []TaskResponse `json:"items"`
	Total int64          `json:"total"`
	Page  int            `json:"page"`
	Size  int            `json:"size"`
}

type MyBooksAnalysisResponse struct {
	MyBooksID      int64         `json:"mybooks_id"`
	BookID         string        `json:"book_id"`
	BookStatus     string        `json:"book_status"`
	AnalysisStatus string        `json:"analysis_status"`
	IngestTask     *TaskResponse `json:"ingest_task,omitempty"`
	SummarizeTask  *TaskResponse `json:"summarize_task,omitempty"`
	ReadingGuide   string        `json:"reading_guide"`
	ErrorMsg       string        `json:"error_msg,omitempty"`
}

func NewMyBooksAnalysisResponse(book models.Book, ingest, summarize *models.Task, hasChapters bool) MyBooksAnalysisResponse {
	response := MyBooksAnalysisResponse{
		MyBooksID:    book.MyBooksID.Int64,
		BookID:       book.ID,
		BookStatus:   book.Status,
		ReadingGuide: book.ReadingGuide,
	}
	if ingest != nil {
		task := NewTaskResponse(*ingest)
		response.IngestTask = &task
	}
	if summarize != nil {
		task := NewTaskResponse(*summarize)
		response.SummarizeTask = &task
	}

	switch {
	case ingest == nil:
		response.AnalysisStatus = models.TaskStatusPending
	case ingest.Status == models.TaskStatusFailed || ingest.Status == models.TaskStatusCanceled:
		response.AnalysisStatus = models.TaskStatusFailed
	case ingest.Status == models.TaskStatusPending || ingest.Status == models.TaskStatusProcessing:
		response.AnalysisStatus = ingest.Status
	case ingest.Status != models.TaskStatusCompleted:
		response.AnalysisStatus = models.TaskStatusFailed
		response.ErrorMsg = "unknown ingest task status"
	case summarize == nil && book.Status == models.BookStatusReady && !hasChapters:
		response.AnalysisStatus = models.TaskStatusFailed
		response.ErrorMsg = "book has no chapters to summarize"
	case summarize == nil:
		response.AnalysisStatus = models.TaskStatusProcessing
	case summarize.Status == models.TaskStatusCompleted:
		response.AnalysisStatus = models.TaskStatusCompleted
	case summarize.Status == models.TaskStatusPending || summarize.Status == models.TaskStatusProcessing:
		response.AnalysisStatus = summarize.Status
	case summarize.Status == models.TaskStatusFailed || summarize.Status == models.TaskStatusCanceled:
		response.AnalysisStatus = models.TaskStatusFailed
	default:
		response.AnalysisStatus = models.TaskStatusFailed
		response.ErrorMsg = "unknown summarize task status"
	}
	return response
}

// Worker -> Core API callback payloads.

type TaskProgressCallback struct {
	Progress int    `json:"progress"`
	Stage    string `json:"stage"`
	Message  string `json:"message"`
}

type TaskCompleteCallback struct {
	Book     BookMetaCallback      `json:"book"`
	Chapters []ChapterMetaCallback `json:"chapters"`
	Chunks   []ChunkMetaCallback   `json:"chunks"`
}

type BookMetaCallback struct {
	Title    string `json:"title"`
	Author   string `json:"author"`
	Language string `json:"language"`
}

type ChapterMetaCallback struct {
	ID        string `json:"id"`
	Title     string `json:"title"`
	Level     int    `json:"level"`
	SortOrder int    `json:"sort_order"`
	Content   string `json:"content"`
}

type ChunkMetaCallback struct {
	ID         string `json:"id"`
	ChapterID  string `json:"chapter_id"`
	Content    string `json:"content"`
	Position   int    `json:"position"`
	TokenCount int    `json:"token_count"`
	VectorID   string `json:"vector_id"`
}

type TaskFailCallback struct {
	ErrorMsg string `json:"error_msg"`
}
