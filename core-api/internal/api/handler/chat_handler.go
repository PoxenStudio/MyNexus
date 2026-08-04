package handler

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/service"
)

type ChatHandler struct {
	chats  *service.ChatService
	worker *coordinator.WorkerClient
}

func NewChatHandler(chats *service.ChatService, worker *coordinator.WorkerClient) *ChatHandler {
	return &ChatHandler{chats: chats, worker: worker}
}

// Completions proxies to Worker's streaming /internal/chat and relays the SSE
// response through unchanged (docs/系统设计文档.md §1.3 "SSE 流式代理"), while
// persisting the user message up front and the assembled assistant reply +
// citations once the stream ends.
func (h *ChatHandler) Completions(c *gin.Context) {
	var req dto.ChatCompletionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	sessionID := req.SessionID
	if sessionID == "" {
		bookIDsJSON, _ := json.Marshal(req.BookIDs)
		session, err := h.chats.CreateSession(defaultUserID, string(bookIDsJSON))
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		sessionID = session.ID
	}

	lastUserMessage := req.Messages[len(req.Messages)-1]
	_ = h.chats.AppendMessage(sessionID, lastUserMessage.Role, lastUserMessage.Content, "[]")

	messages := make([]coordinator.ChatMessage, 0, len(req.Messages))
	for _, m := range req.Messages {
		messages = append(messages, coordinator.ChatMessage{Role: m.Role, Content: m.Content})
	}

	body, err := h.worker.Chat(coordinator.ChatRequest{Messages: messages, BookIDs: req.BookIDs, TopK: 5})
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "chat failed: " + err.Error()})
		return
	}
	defer body.Close()

	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("X-Session-Id", sessionID)
	c.Status(http.StatusOK)

	var answer strings.Builder
	citationsJSON := "[]"

	scanner := bufio.NewScanner(body)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := scanner.Text()
		fmt.Fprintf(c.Writer, "%s\n", line)
		c.Writer.Flush()

		data, ok := strings.CutPrefix(line, "data: ")
		if !ok || data == "[DONE]" {
			continue
		}
		var event struct {
			Choices []struct {
				Delta struct {
					Content string `json:"content"`
				} `json:"delta"`
			} `json:"choices"`
			Citations json.RawMessage `json:"citations"`
		}
		if json.Unmarshal([]byte(data), &event) != nil {
			continue
		}
		if len(event.Choices) > 0 {
			answer.WriteString(event.Choices[0].Delta.Content)
		}
		if len(event.Citations) > 0 {
			citationsJSON = string(event.Citations)
		}
	}

	_ = h.chats.AppendMessage(sessionID, "assistant", answer.String(), citationsJSON)
	_ = h.chats.TouchSession(sessionID)
}

func (h *ChatHandler) ListSessions(c *gin.Context) {
	sessions, err := h.chats.ListSessions(defaultUserID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	items := make([]dto.ChatSessionResponse, 0, len(sessions))
	for _, s := range sessions {
		items = append(items, dto.NewChatSessionResponse(s))
	}
	c.JSON(http.StatusOK, dto.ChatSessionListResponse{Items: items})
}

func (h *ChatHandler) GetSession(c *gin.Context) {
	id := c.Param("id")
	session, err := h.chats.GetSession(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "session not found"})
		return
	}
	messages, err := h.chats.ListMessages(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	items := make([]dto.ChatMessageResponse, 0, len(messages))
	for _, m := range messages {
		items = append(items, dto.NewChatMessageResponse(m))
	}
	c.JSON(http.StatusOK, dto.ChatSessionDetailResponse{
		ChatSessionResponse: dto.NewChatSessionResponse(*session), Messages: items,
	})
}

func (h *ChatHandler) DeleteSession(c *gin.Context) {
	id := c.Param("id")
	if err := h.chats.DeleteSession(id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.Status(http.StatusNoContent)
}
