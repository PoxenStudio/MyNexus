package dto

import (
	"encoding/json"
	"sort"

	"mynexus/core-api/internal/models"
)

// KeywordResponse is one whole-book content keyword — extracted from the
// text itself (see worker/src/pipelines/summary.py), distinct from Tags
// (user-/MyBooks-assigned labels).
type KeywordResponse struct {
	Term   string  `json:"term"`
	Weight float64 `json:"weight"`
}

type BookResponse struct {
	ID           string            `json:"id"`
	UserID       string            `json:"user_id"`
	Title        string            `json:"title"`
	Author       string            `json:"author"`
	Publisher    string            `json:"publisher"`
	Language     string            `json:"language"`
	PublishDate  string            `json:"publish_date"`
	ISBN         string            `json:"isbn"`
	SourceOrigin string            `json:"source_origin"`
	SourceFormat string            `json:"source_format"`
	Status       string            `json:"status"`
	Tags         []string          `json:"tags"`
	Category     string            `json:"category"`
	Summary      string            `json:"summary"`
	Keywords     []KeywordResponse `json:"keywords"`
	// CoverURL is "" if the book has no cover yet (not yet ingested, or
	// ingestion produced nothing usable — see grpcserver.ReportComplete),
	// otherwise "/books/{id}/cover" (relative to apiClient's base URL, which
	// already includes "/api/v1" — see web-ui/src/api/client.ts, and
	// AuthHandler's avatarURL for the same pattern). Never the original
	// cover_url or on-disk cover_path — those are download/storage details,
	// not something callers should see or depend on.
	CoverURL  string `json:"cover_url"`
	CreatedAt string `json:"created_at"`
	UpdatedAt string `json:"updated_at"`
}

// NewBookResponse truncates Keywords to maxKeywords (config.KeywordConfig —
// see the system settings page), sorted by weight descending first so
// raising the limit later always surfaces the next-highest-weight terms
// already sitting in storage, no re-summarization needed. Pass maxKeywords
// <= 0 to skip truncation (e.g. an internal caller that wants everything).
func NewBookResponse(b models.Book, maxKeywords int) BookResponse {
	var tags []string
	_ = json.Unmarshal([]byte(b.Tags), &tags)
	if tags == nil {
		tags = []string{}
	}

	var keywords []KeywordResponse
	_ = json.Unmarshal([]byte(b.Keywords), &keywords)
	if keywords == nil {
		keywords = []KeywordResponse{}
	}
	sort.Slice(keywords, func(i, j int) bool { return keywords[i].Weight > keywords[j].Weight })
	if maxKeywords > 0 && len(keywords) > maxKeywords {
		keywords = keywords[:maxKeywords]
	}

	coverURL := ""
	if b.CoverPath != "" {
		coverURL = "/books/" + b.ID + "/cover"
	}

	return BookResponse{
		ID: b.ID, UserID: b.UserID, Title: b.Title, Author: b.Author, Publisher: b.Publisher,
		Language: b.Language, PublishDate: b.PublishDate, ISBN: b.ISBN, SourceOrigin: b.SourceOrigin,
		SourceFormat: b.SourceFormat, Status: b.Status, Tags: tags, Category: b.Category, Summary: b.Summary,
		Keywords: keywords, CoverURL: coverURL, CreatedAt: b.CreatedAt, UpdatedAt: b.UpdatedAt,
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
	// Language is optional — an external caller (e.g. MyBooks, which does
	// its own title-based language detection) can pass a language code here
	// to override whatever ingestion auto-detected; an empty string leaves
	// the existing value untouched (see BookService.UpdateBook).
	Language string `json:"language"`
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
