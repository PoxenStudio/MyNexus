package dto

import (
	"encoding/json"

	"mynexus/core-api/internal/models"
)

type ChatMessageInput struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatCompletionRequest struct {
	SessionID string             `json:"session_id"`
	Messages  []ChatMessageInput `json:"messages" binding:"required,min=1"`
	BookIDs   []string           `json:"book_ids"`
	Stream    bool               `json:"stream"`
}

type ChatSessionResponse struct {
	ID        string   `json:"id"`
	Title     string   `json:"title"`
	BookIDs   []string `json:"book_ids"`
	CreatedAt string   `json:"created_at"`
	UpdatedAt string   `json:"updated_at"`
}

func NewChatSessionResponse(s models.ChatSession) ChatSessionResponse {
	var bookIDs []string
	_ = json.Unmarshal([]byte(s.BookIDs), &bookIDs)
	if bookIDs == nil {
		bookIDs = []string{}
	}
	return ChatSessionResponse{ID: s.ID, Title: s.Title, BookIDs: bookIDs, CreatedAt: s.CreatedAt, UpdatedAt: s.UpdatedAt}
}

type ChatMessageResponse struct {
	ID        string          `json:"id"`
	Role      string          `json:"role"`
	Content   string          `json:"content"`
	Citations json.RawMessage `json:"citations"`
	CreatedAt string          `json:"created_at"`
}

func NewChatMessageResponse(m models.ChatMessage) ChatMessageResponse {
	citations := m.Citations
	if citations == "" {
		citations = "[]"
	}
	return ChatMessageResponse{
		ID: m.ID, Role: m.Role, Content: m.Content, Citations: json.RawMessage(citations), CreatedAt: m.CreatedAt,
	}
}

type ChatSessionDetailResponse struct {
	ChatSessionResponse
	Messages []ChatMessageResponse `json:"messages"`
}

type ChatSessionListResponse struct {
	Items []ChatSessionResponse `json:"items"`
}
