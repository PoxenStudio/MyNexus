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
	CreatedAt    string
	UpdatedAt    string
}
