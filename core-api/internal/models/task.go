package models

const (
	TaskStatusPending    = "pending"
	TaskStatusProcessing = "processing"
	TaskStatusCompleted  = "completed"
	TaskStatusFailed     = "failed"
)

const (
	TaskTypeIngest = "ingest"
)

type Task struct {
	ID        string
	BookID    string
	UserID    string
	Type      string
	Status    string
	Progress  int
	ErrorMsg  string
	StagesLog string // JSON array, stored as-is
	CreatedAt string
	UpdatedAt string
}
