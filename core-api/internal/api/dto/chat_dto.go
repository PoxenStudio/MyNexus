package dto

import (
	"encoding/json"

	"mynexus/core-api/internal/models"
)

type ReadingContextInput struct {
	BookTitle        string  `json:"book_title"`
	ChapterTitle     string  `json:"chapter_title"`
	ChapterHref      string  `json:"chapter_href"`
	SectionIndex     int32   `json:"section_index"`
	ProgressFraction float64 `json:"progress_fraction"`
	Page             int32   `json:"page"`
	CFI              string  `json:"cfi"`
	Snippet          string  `json:"snippet"`
}

type SelectionContextInput struct {
	Text             string  `json:"text"`
	ChapterTitle     string  `json:"chapter_title"`
	ChapterHref      string  `json:"chapter_href"`
	SectionIndex     int32   `json:"section_index"`
	Page             int32   `json:"page"`
	ProgressFraction float64 `json:"progress_fraction"`
	CFI              string  `json:"cfi"`
}

type ChatContextInput struct {
	Reading   *ReadingContextInput   `json:"reading,omitempty"`
	Selection *SelectionContextInput `json:"selection,omitempty"`
}

const (
	maxSelectionChars = 2000
	maxTitleChars     = 200
	maxHrefChars      = 500
	maxCFIChars       = 500
	maxSnippetChars   = 50
)

func truncateRunes(value string, limit int) string {
	runes := []rune(value)
	if len(runes) <= limit {
		return value
	}
	return string(runes[:limit])
}

// Normalize enforces the wire limits from MyReader/MyBooks. It returns false
// when the context carries no usable field and should be dropped entirely.
func (c *ChatContextInput) Normalize() bool {
	if c == nil {
		return false
	}
	if c.Reading != nil {
		r := c.Reading
		r.BookTitle = truncateRunes(r.BookTitle, maxTitleChars)
		r.ChapterTitle = truncateRunes(r.ChapterTitle, maxTitleChars)
		r.ChapterHref = truncateRunes(r.ChapterHref, maxHrefChars)
		r.CFI = truncateRunes(r.CFI, maxCFIChars)
		r.Snippet = truncateRunes(r.Snippet, maxSnippetChars)
		if r.ProgressFraction < 0 || r.ProgressFraction > 1 {
			r.ProgressFraction = 0
		}
		if r.SectionIndex < 0 {
			r.SectionIndex = 0
		}
		if r.Page < 0 {
			r.Page = 0
		}
	}
	if c.Selection != nil {
		s := c.Selection
		s.Text = truncateRunes(s.Text, maxSelectionChars)
		s.ChapterTitle = truncateRunes(s.ChapterTitle, maxTitleChars)
		s.ChapterHref = truncateRunes(s.ChapterHref, maxHrefChars)
		s.CFI = truncateRunes(s.CFI, maxCFIChars)
		if s.ProgressFraction < 0 || s.ProgressFraction > 1 {
			s.ProgressFraction = 0
		}
		if s.SectionIndex < 0 {
			s.SectionIndex = 0
		}
		if s.Page < 0 {
			s.Page = 0
		}
		if s.Text == "" {
			c.Selection = nil
		}
	}
	return c.Reading != nil || c.Selection != nil
}

type ChatMessageInput struct {
	Role    string            `json:"role"`
	Content string            `json:"content"`
	Context *ChatContextInput `json:"context,omitempty"`
}

type ChatCompletionRequest struct {
	SessionID string             `json:"session_id"`
	Messages  []ChatMessageInput `json:"messages" binding:"required,min=1"`
	BookIDs   []string           `json:"book_ids"`
	Stream    bool               `json:"stream"`
}

// CitationResponse mirrors the shape Worker's QAPipeline has always emitted
// (chunk_id/chapter_id/book_id/score/content) — the SSE payload's JSON field
// names are unchanged by the gRPC migration, only how Core API gets this data
// from Worker changed (a gRPC ChatChunk.citations field now, not a raw SSE
// "citations" JSON key relayed byte-for-byte).
type CitationResponse struct {
	ChunkID     string  `json:"chunk_id"`
	ChapterID   string  `json:"chapter_id"`
	BookID      string  `json:"book_id"`
	Score       float64 `json:"score"`
	Content     string  `json:"content"`
	StartOffset int     `json:"start_offset,omitempty"`
	EndOffset   int     `json:"end_offset,omitempty"`
}

type RenameSessionRequest struct {
	Title string `json:"title" binding:"required"`
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

// ToolResultResponse mirrors a single forwarded SSE tool_result frame.
type ToolResultResponse struct {
	ToolName   string `json:"tool_name"`
	ResultJSON string `json:"result_json"`
}

type ChatMessageResponse struct {
	ID        string          `json:"id"`
	Role      string          `json:"role"`
	Content   string          `json:"content"`
	Citations json.RawMessage `json:"citations"`
	// ToolResults mirrors the SSE tool_result frames ({tool_name, result_json})
	// persisted with the message, so the client can re-render visuals such as
	// the mindmap card when it reloads history.
	ToolResults json.RawMessage `json:"tool_results"`
	// Context holds the reading position / selection snapshot captured when the
	// message was sent, so history replay can show the quoted passage again.
	Context   json.RawMessage `json:"context"`
	CreatedAt string          `json:"created_at"`
}

func NewChatMessageResponse(m models.ChatMessage) ChatMessageResponse {
	citations := m.Citations
	if citations == "" {
		citations = "[]"
	}
	toolResults := m.ToolResults
	if toolResults == "" {
		toolResults = "[]"
	}
	contextJSON := m.ContextJSON
	if contextJSON == "" {
		contextJSON = "{}"
	}
	return ChatMessageResponse{
		ID: m.ID, Role: m.Role, Content: m.Content, Citations: json.RawMessage(citations),
		ToolResults: json.RawMessage(toolResults), Context: json.RawMessage(contextJSON),
		CreatedAt: m.CreatedAt,
	}
}

type ChatSessionDetailResponse struct {
	ChatSessionResponse
	Messages []ChatMessageResponse `json:"messages"`
}

type ChatSessionListResponse struct {
	Items []ChatSessionResponse `json:"items"`
}
