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
	Summary   string
	CreatedAt string
	UpdatedAt string
}
