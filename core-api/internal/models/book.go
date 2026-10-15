package models

import "database/sql"

const (
	BookStatusPending    = "pending"
	BookStatusProcessing = "processing"
	BookStatusReady      = "ready"
	BookStatusFailed     = "failed"
)

const (
	SourceOriginDirectUpload = "DirectUpload"
	SourceOriginMyBooks      = "MyBooks"
)

type Book struct {
	ID           string
	UserID       string
	Title        string
	Author       string
	Publisher    string
	Language     string
	PublishDate  string
	ISBN         string
	SourceOrigin string
	SourceFormat string
	FilePath     string
	Status       string
	Tags         string // JSON array, stored as-is
	Category     string
	// Summary is the whole-book summary produced by the map-reduce
	// summarization pipeline (see worker/src/pipelines/summary.py); empty
	// until a summarize task completes for this book.
	Summary string
	// Keywords is a JSON array of {"term","weight"} objects, reduced from
	// each chapter's summary during summarization (ReportBookSummary) —
	// content keywords, distinct from Tags (user-/MyBooks-assigned labels).
	// Stored unsorted-length (not pre-truncated); the read path truncates to
	// config.KeywordConfig.MaxKeywords so raising that setting later doesn't
	// require re-summarizing. Empty until a summarize task completes.
	Keywords string // JSON array, stored as-is
	// ReadingGuide is a LLM-generated reading guide produced alongside the
	// whole-book summary — preview/review/discuss prompts driven by the
	// chapter summaries and the whole-book summary. Empty until the
	// summarize pipeline runs and succeeds.
	ReadingGuide string
	// ReferenceIndex is the worker's post-summary LLM pass that scans the
	// chapter summaries for cited/referenced external works and tallies them
	// by frequency (see worker/src/skills/catalog.py's reference-index).
	// Stored as plain markdown text so it renders directly in the detail page
	// — not JSON, because it's consumed purely as prose.
	ReferenceIndex string
	// CoverPath is the local on-disk path to the cover image (see
	// BookService's coverDir/SetCover), empty until one is downloaded,
	// extracted, or generated — see storage/sqlite/migrations/0008_book_cover.sql.
	CoverPath string
	MyBooksID sql.NullInt64
	CreatedAt string
	UpdatedAt string
}
