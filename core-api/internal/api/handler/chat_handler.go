package handler

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
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

// sseEvent is the same wire shape the browser has always received (see
// web-ui/src/api/chat.ts) — Core API builds these itself now from gRPC
// ChatEvents instead of relaying raw SSE bytes read off an HTTP body, but the
// browser-facing contract is unchanged by the gRPC migration.
type sseEvent struct {
	Choices []struct {
		Delta struct {
			Content string `json:"content"`
		} `json:"delta"`
	} `json:"choices"`
	Citations json.RawMessage `json:"citations,omitempty"`
}

// Completions calls Worker's streaming Chat RPC and relays it to the browser
// as SSE (docs/系统设计文档.md §1.3 "SSE 流式代理" — the browser-facing leg stays
// HTTP/SSE; only the Core API <-> Worker leg is gRPC, see
// .claude/memory/mynexus_grpc_migration.md), while persisting the user
// message up front and the assembled assistant reply + citations once the
// stream ends.
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

	stream, err := h.worker.Chat(coordinator.ChatRequest{Messages: messages, BookIDs: req.BookIDs, TopK: 5})
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "chat failed: " + err.Error()})
		return
	}

	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("X-Session-Id", sessionID)
	c.Status(http.StatusOK)

	var answer strings.Builder
	citationsJSON := "[]"

	for {
		event, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			break // Worker died/disconnected mid-stream — end the SSE stream gracefully.
		}

		var frame sseEvent
		if event.Delta != "" {
			answer.WriteString(event.Delta)
			frame.Choices = []struct {
				Delta struct {
					Content string `json:"content"`
				} `json:"delta"`
			}{{Delta: struct {
				Content string `json:"content"`
			}{Content: event.Delta}}}
		}
		if event.Citations != nil {
			citations := make([]dto.CitationResponse, 0, len(event.Citations))
			for _, cit := range event.Citations {
				citations = append(citations, dto.CitationResponse{
					ChunkID: cit.ChunkID, ChapterID: cit.ChapterID, BookID: cit.BookID,
					Score: cit.Score, Content: cit.Content,
				})
			}
			citationsBytes, _ := json.Marshal(citations)
			citationsJSON = string(citationsBytes)
			frame.Citations = json.RawMessage(citationsBytes)
		}

		payload, _ := json.Marshal(frame)
		fmt.Fprintf(c.Writer, "data: %s\n\n", payload)
		c.Writer.Flush()
	}
	fmt.Fprint(c.Writer, "data: [DONE]\n\n")
	c.Writer.Flush()

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
