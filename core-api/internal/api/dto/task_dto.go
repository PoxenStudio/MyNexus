package dto

import (
	"encoding/json"

	"mynexus/core-api/internal/models"
)

type TaskResponse struct {
	ID        string                 `json:"id"`
	BookID    string                 `json:"book_id"`
	Type      string                 `json:"type"`
	Status    string                 `json:"status"`
	Progress  int                    `json:"progress"`
	ErrorMsg  string                 `json:"error_msg"`
	StagesLog []models.StageLogEntry `json:"stages_log"`
	CreatedAt string                 `json:"created_at"`
	UpdatedAt string                 `json:"updated_at"`
}

func NewTaskResponse(t models.Task) TaskResponse {
	stagesLog := []models.StageLogEntry{}
	_ = json.Unmarshal([]byte(t.StagesLog), &stagesLog)
	return TaskResponse{
		ID: t.ID, BookID: t.BookID, Type: t.Type, Status: t.Status, Progress: t.Progress,
		ErrorMsg: t.ErrorMsg, StagesLog: stagesLog, CreatedAt: t.CreatedAt, UpdatedAt: t.UpdatedAt,
	}
}

type TaskListResponse struct {
	Items []TaskResponse `json:"items"`
	Total int64          `json:"total"`
	Page  int            `json:"page"`
	Size  int            `json:"size"`
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
