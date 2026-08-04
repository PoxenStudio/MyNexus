package models

type ChatSession struct {
	ID        string
	UserID    string
	Title     string
	BookIDs   string // JSON array, stored as-is
	CreatedAt string
	UpdatedAt string
}

const (
	ChatRoleUser      = "user"
	ChatRoleAssistant = "assistant"
)

type ChatMessage struct {
	ID        string
	SessionID string
	Role      string
	Content   string
	Citations string // JSON array, stored as-is
	CreatedAt string
}
