package dto

import (
	"encoding/json"

	"mynexus/core-api/internal/models"
)

type BookResponse struct {
	ID           string   `json:"id"`
	UserID       string   `json:"user_id"`
	Title        string   `json:"title"`
	Author       string   `json:"author"`
	Publisher    string   `json:"publisher"`
	Language     string   `json:"language"`
	PublishDate  string   `json:"publish_date"`
	ISBN         string   `json:"isbn"`
	SourceOrigin string   `json:"source_origin"`
	SourceFormat string   `json:"source_format"`
	Status       string   `json:"status"`
	Tags         []string `json:"tags"`
	Category     string   `json:"category"`
	CreatedAt    string   `json:"created_at"`
	UpdatedAt    string   `json:"updated_at"`
}

func NewBookResponse(b models.Book) BookResponse {
	var tags []string
	_ = json.Unmarshal([]byte(b.Tags), &tags)
	if tags == nil {
		tags = []string{}
	}
	return BookResponse{
		ID: b.ID, UserID: b.UserID, Title: b.Title, Author: b.Author, Publisher: b.Publisher,
		Language: b.Language, PublishDate: b.PublishDate, ISBN: b.ISBN, SourceOrigin: b.SourceOrigin,
		SourceFormat: b.SourceFormat, Status: b.Status, Tags: tags, Category: b.Category,
		CreatedAt: b.CreatedAt, UpdatedAt: b.UpdatedAt,
	}
}

type ChapterResponse struct {
	ID        string `json:"id"`
	Title     string `json:"title"`
	Level     int    `json:"level"`
	SortOrder int    `json:"sort_order"`
	Summary   string `json:"summary"`
}

func NewChapterResponse(c models.Chapter) ChapterResponse {
	return ChapterResponse{ID: c.ID, Title: c.Title, Level: c.Level, SortOrder: c.SortOrder, Summary: c.Summary}
}

type BookDetailResponse struct {
	BookResponse
	Chapters []ChapterResponse `json:"chapters"`
}

type BookListResponse struct {
	Items []BookResponse `json:"items"`
	Total int64          `json:"total"`
	Page  int            `json:"page"`
	Size  int            `json:"size"`
}

type UpdateBookRequest struct {
	Title    string   `json:"title"`
	Author   string   `json:"author"`
	Category string   `json:"category"`
	Tags     []string `json:"tags"`
}

type ImportResponse struct {
	TaskID string `json:"task_id"`
	BookID string `json:"book_id"`
}

type ChunkResponse struct {
	ID         string `json:"id"`
	ChapterID  string `json:"chapter_id"`
	Content    string `json:"content"`
	TokenCount int    `json:"token_count"`
	Position   int    `json:"position"`
	VectorID   string `json:"vector_id"`
}

func NewChunkResponse(c models.Chunk) ChunkResponse {
	return ChunkResponse{
		ID: c.ID, ChapterID: c.ChapterID, Content: c.Content,
		TokenCount: c.TokenCount, Position: c.Position, VectorID: c.VectorID,
	}
}

type ChunkListResponse struct {
	Items []ChunkResponse `json:"items"`
	Total int64           `json:"total"`
	Page  int             `json:"page"`
	Size  int             `json:"size"`
}

// BulkBookRequest is the body for POST /books/bulk-delete and
// /books/bulk-rebuild (需求文档.md §6.7.3 "批量选择书籍并执行删除或重建操作").
type BulkBookRequest struct {
	IDs []string `json:"ids" binding:"required,min=1"`
}

type BulkResultItem struct {
	ID    string `json:"id"`
	OK    bool   `json:"ok"`
	Error string `json:"error,omitempty"`
}

type BulkResultResponse struct {
	Items []BulkResultItem `json:"items"`
}

type RebuildResponse struct {
	TaskID string `json:"task_id"`
	BookID string `json:"book_id"`
}
