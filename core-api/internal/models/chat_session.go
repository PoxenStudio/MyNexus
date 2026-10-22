package models

type ChatSession struct {
	ID                 string
	UserID             string
	Title              string
	BookIDs            string // JSON array, stored as-is
	MemorySummary      string
	MemoryUpdatedAt    string
	MemoryMessageCount int
	CreatedAt          string
	UpdatedAt          string
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
	// ToolResults is a JSON array of forwarded tool_result frames
	// ({tool_name, result_json}, see chat_handler.go). Persisted so history
	// reads can re-render visuals like the mindmap card.
	ToolResults string
	// ContextJSON 是发送该消息时的阅读位置与选区快照，assistant 消息为空。
	ContextJSON string
	CreatedAt   string
}
