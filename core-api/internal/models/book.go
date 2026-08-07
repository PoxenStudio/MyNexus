package models

// Book statuses, mirroring docs/系统设计文档.md §5.2.
const (
	BookStatusPending    = "pending"
	BookStatusProcessing = "processing"
	BookStatusReady      = "ready"
	BookStatusFailed     = "failed"
)

const (
	SourceOriginDirectUpload = "DirectUpload"
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
	// CoverPath is the local on-disk path to the cover image (see
	// BookService's coverDir/SetCover), empty until one is downloaded,
	// extracted, or generated — see storage/sqlite/migrations/0008_book_cover.sql.
	CoverPath string
	CreatedAt string
	UpdatedAt string
}
