package models

const (
	TaskStatusPending    = "pending"
	TaskStatusProcessing = "processing"
	TaskStatusCompleted  = "completed"
	TaskStatusFailed     = "failed"
)

const (
	TaskTypeIngest    = "ingest"
	TaskTypeSummarize = "summarize"
)

type Task struct {
	ID        string
	BookID    string
	UserID    string
	Type      string
	Status    string
	Progress  int
	ErrorMsg  string
	StagesLog string // JSON array of StageLogEntry, stored as-is
	// DispatchedAt is "" while the task is still queued, waiting for a free
	// worker.max_concurrent_tasks slot (see internal/dispatch.Dispatcher) —
	// set once it's actually been handed to Worker. Distinct from Status:
	// a queued task and a dispatched-but-not-yet-progressed one are both
	// still TaskStatusPending.
	DispatchedAt string
	CreatedAt    string
	UpdatedAt    string
}

// StageLogEntry is one entry in a Task's stages_log JSON array — a structured
// record of pipeline stage transitions (parsing, splitting, embedding, ...),
// as opposed to the single flat error_msg string.
type StageLogEntry struct {
	Stage    string `json:"stage"`
	Message  string `json:"message,omitempty"`
	Progress int    `json:"progress"`
	At       string `json:"at"`
}
