package handler

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/service"
)

type ChatHandler struct {
	chats  *service.ChatService
	worker *coordinator.WorkerClient
	// maxSessions is config.ChatConfig.MaxSessions, snapshotted at router
	// wiring time (like RequireChatEnabled's cfg.Chat.Enabled) — see
	// ChatService.EnforceSessionLimit.
	maxSessions       int
	slidingWindowSize int
	cfg               *config.Config
}

func NewChatHandler(chats *service.ChatService, worker *coordinator.WorkerClient, cfg *config.Config) *ChatHandler {
	return &ChatHandler{
		chats: chats, worker: worker,
		maxSessions: cfg.Chat.MaxSessions, slidingWindowSize: cfg.Chat.SlidingWindowSize, cfg: cfg,
	}
}

// citationsEnabled re-reads config.yaml each call so the system settings
// toggle applies to the next message without restarting Core API.
func (h *ChatHandler) citationsEnabled() bool {
	cfg, err := config.LoadFromFile()
	if err != nil {
		return h.cfg.Chat.ReturnCitations
	}
	return cfg.Chat.ReturnCitations
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
	Citations  json.RawMessage `json:"citations,omitempty"`
	ToolResult *struct {
		ToolName   string `json:"tool_name"`
		ResultJSON string `json:"result_json"`
	} `json:"tool_result,omitempty"`
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

	userID := c.GetString("user_id")

	sessionID := req.SessionID
	if sessionID == "" {
		bookIDsJSON, _ := json.Marshal(req.BookIDs)
		session, err := h.chats.CreateSession(userID, string(bookIDsJSON))
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		sessionID = session.ID
		// Prune right after creating, not before — a fresh session always
		// gets through; it's the *next* one over the cap that starts
		// evicting the oldest.
		if err := h.chats.EnforceSessionLimit(userID, h.maxSessions); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
	} else if owned, err := h.sessionOwnedBy(sessionID, userID); err != nil || !owned {
		// Caller passed someone else's session_id (or a stale/deleted one).
		// Per-user isolation (see .claude/memory/mynexus_user_management.md)
		// — never append to or continue a session that isn't the caller's.
		c.JSON(http.StatusNotFound, gin.H{"error": "session not found"})
		return
	}

	if len(req.BookIDs) > 0 {
		if err := h.chats.SetTitleFromFirstBookIfEmpty(sessionID, req.BookIDs); err != nil {
			fmt.Printf("[chat] set title from book failed: %v\n", err)
		}
	}

	lastUserMessage := req.Messages[len(req.Messages)-1]
	contextJSON := buildContextJSON(lastUserMessage)
	_ = h.chats.AppendMessage(sessionID, lastUserMessage.Role, lastUserMessage.Content, "[]", "[]", contextJSON)

	// 历史以 DB 为可信来源装配（滑动窗口 + citations 注入 + 记忆摘要/待压缩旧消息）
	prompt, err := h.chats.BuildChatPrompt(sessionID, h.slidingWindowSize)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "assemble chat history failed: " + err.Error()})
		return
	}
	messages := make([]coordinator.ChatMessage, 0, len(prompt.Messages))
	injected := 0
	for _, m := range prompt.Messages {
		if strings.Contains(m.Content, "上一轮回答参考来源：") {
			injected++
		}
		messages = append(messages, coordinator.ChatMessage{
			Role: m.Role, Content: m.Content, Context: m.ContextJSON,
		})
	}
	older := make([]coordinator.ChatMessage, 0, len(prompt.Older))
	for _, m := range prompt.Older {
		older = append(older, coordinator.ChatMessage{Role: m.Role, Content: m.Content})
	}
	fmt.Printf("[chat] session=%s window=%d history=%d older=%d cursor=%d has_memory=%t citation_msgs=%d\n",
		sessionID, h.slidingWindowSize, len(messages), len(older),
		prompt.MemoryMessageCount, prompt.MemorySummary != "", injected)

	stream, err := h.worker.Chat(coordinator.ChatRequest{
		Messages: messages, BookIDs: req.BookIDs, TopK: 10,
		MemorySummary: prompt.MemorySummary, MemoryMessageCount: prompt.MemoryMessageCount,
		OlderMessages: older,
	})
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
	var streamCitations []dto.CitationResponse
	citationsJSON := "[]"
	returnCitations := h.citationsEnabled()
	toolResults := make([]dto.ToolResultResponse, 0)

	for {
		event, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			break // Worker died/disconnected mid-stream — end the SSE stream gracefully.
		}

		var frame sseEvent

		if event.MemoryUpdate != nil {
			// 记忆事件只落库，不转发浏览器：消费后直接进入下一帧，避免发出空 SSE 帧
			if err := h.chats.UpdateChatMemory(sessionID, event.MemoryUpdate.Summary, event.MemoryUpdate.MessageCount); err != nil {
				fmt.Printf("[chat] update memory failed: %v\n", err)
			}
			continue
		}

		if event.ToolResult != nil {
			frame.ToolResult = &struct {
				ToolName   string `json:"tool_name"`
				ResultJSON string `json:"result_json"`
			}{ToolName: event.ToolResult.ToolName, ResultJSON: event.ToolResult.ResultJSON}
			toolResults = append(toolResults, dto.ToolResultResponse{
				ToolName: event.ToolResult.ToolName, ResultJSON: event.ToolResult.ResultJSON,
			})
		}

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
			streamCitations = make([]dto.CitationResponse, 0, len(event.Citations))
			for _, cit := range event.Citations {
				streamCitations = append(streamCitations, dto.CitationResponse{
					ChunkID: cit.ChunkID, ChapterID: cit.ChapterID, BookID: cit.BookID,
					Score: cit.Score, Content: cit.Content,
					StartOffset: cit.StartOffset, EndOffset: cit.EndOffset,
				})
			}
			if returnCitations {
				citationsBytes, _ := json.Marshal(streamCitations)
				frame.Citations = json.RawMessage(citationsBytes)
			}
		}

		payload, _ := json.Marshal(frame)
		fmt.Fprintf(c.Writer, "data: %s\n\n", payload)
		c.Writer.Flush()
	}
	fmt.Fprint(c.Writer, "data: [DONE]\n\n")
	c.Writer.Flush()

	finalAnswer, finalCitations := finalizeCitations(answer.String(), streamCitations)
	if returnCitations {
		finalCitationsBytes, _ := json.Marshal(finalCitations)
		citationsJSON = string(finalCitationsBytes)
	} else {
		finalAnswer = stripCitationMarkers(finalAnswer)
	}
	toolResultsBytes, _ := json.Marshal(toolResults)
	fmt.Printf("[chat] session=%s tool_results=%d citations=%d return_citations=%t\n",
		sessionID, len(toolResults), len(finalCitations), returnCitations)

	_ = h.chats.AppendMessage(sessionID, "assistant", finalAnswer, citationsJSON, string(toolResultsBytes), "{}")
	_ = h.chats.TouchSession(sessionID)

	if len(req.BookIDs) == 0 && len(finalCitations) > 0 {
		firstBookID := finalCitations[0].BookID
		if err := h.chats.SetTitleFromFirstBookIfEmpty(sessionID, []string{firstBookID}); err != nil {
			fmt.Printf("[chat] set title from citation book failed: %v\n", err)
		}
	}
}

// buildContextJSON 裁剪并序列化阅读位置/选区快照。超出总量上限时先丢弃选区，
// 仍超限则整段上下文丢弃，保证不影响普通问答。
func buildContextJSON(msg dto.ChatMessageInput) string {
	if msg.Context == nil || !msg.Context.Normalize() {
		return "{}"
	}
	raw, err := json.Marshal(msg.Context)
	if err != nil {
		fmt.Printf("[chat] marshal context failed: %v\n", err)
		return "{}"
	}
	if len(raw) <= 8*1024 {
		return string(raw)
	}
	msg.Context.Selection = nil
	raw, err = json.Marshal(msg.Context)
	if err != nil || len(raw) > 8*1024 {
		fmt.Printf("[chat] context dropped, size=%d\n", len(raw))
		return "{}"
	}
	return string(raw)
}

// sessionOwnedBy reports whether sessionID exists and belongs to userID.
// Every per-session route (Get/Rename/Delete, and Completions when it's
// handed an existing session_id) goes through this before touching a
// session, so one user can never read, rename, delete, or piggyback
// messages onto another user's conversation — see
// .claude/memory/mynexus_user_management.md.
func (h *ChatHandler) sessionOwnedBy(sessionID, userID string) (bool, error) {
	session, err := h.chats.GetSession(sessionID)
	if err == sql.ErrNoRows {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return session.UserID == userID, nil
}

func (h *ChatHandler) ListSessions(c *gin.Context) {
	sessions, err := h.chats.ListSessions(c.GetString("user_id"))
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
	if owned, err := h.sessionOwnedBy(id, c.GetString("user_id")); err != nil || !owned {
		c.JSON(http.StatusNotFound, gin.H{"error": "session not found"})
		return
	}
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
	returnCitations := h.citationsEnabled()
	for _, m := range messages {
		item := dto.NewChatMessageResponse(m)
		if !returnCitations {
			item.Citations = json.RawMessage("[]")
			item.Content = stripCitationMarkers(item.Content)
		}
		items = append(items, item)
	}
	c.JSON(http.StatusOK, dto.ChatSessionDetailResponse{
		ChatSessionResponse: dto.NewChatSessionResponse(*session), Messages: items,
	})
}

func (h *ChatHandler) RenameSession(c *gin.Context) {
	id := c.Param("id")
	if owned, err := h.sessionOwnedBy(id, c.GetString("user_id")); err != nil || !owned {
		c.JSON(http.StatusNotFound, gin.H{"error": "session not found"})
		return
	}
	var req dto.RenameSessionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if err := h.chats.RenameSession(id, req.Title); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.Status(http.StatusNoContent)
}

func (h *ChatHandler) DeleteSession(c *gin.Context) {
	id := c.Param("id")
	if owned, err := h.sessionOwnedBy(id, c.GetString("user_id")); err != nil || !owned {
		c.JSON(http.StatusNotFound, gin.H{"error": "session not found"})
		return
	}
	if err := h.chats.DeleteSession(id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.Status(http.StatusNoContent)
}

var citedIndexRE = regexp.MustCompile(`\[(\d+)\]`)
var trailingCiteLineRE = regexp.MustCompile("(?m)^[\\s\u3000]*\\[\\d+\\](?:\\s*\\[\\d+\\])*\\s*$")

func stripCitationMarkers(answer string) string {
	answer = trailingCiteLineRE.ReplaceAllString(answer, "")
	answer = citedIndexRE.ReplaceAllString(answer, "")
	answer = regexp.MustCompile("(?m)^[ \\t\u3000]+$").ReplaceAllString(answer, "")
	answer = regexp.MustCompile(`\n{3,}`).ReplaceAllString(answer, "\n\n")
	return strings.TrimRight(answer, "\n \u3000")
}

func finalizeCitations(answer string, citations []dto.CitationResponse) (string, []dto.CitationResponse) {
	matches := citedIndexRE.FindAllStringSubmatchIndex(answer, -1)
	if len(matches) == 0 {
		return answer, citations
	}
	seen := map[int]int{}
	var order []int
	for _, m := range matches {
		n, err := strconv.Atoi(answer[m[2]:m[3]])
		if err != nil {
			continue
		}
		if _, ok := seen[n]; !ok {
			seen[n] = len(order) + 1
			order = append(order, n)
		}
	}
	if len(order) == 0 {
		return answer, citations
	}

	answer = citedIndexRE.ReplaceAllStringFunc(answer, func(s string) string {
		n, err := strconv.Atoi(s[1 : len(s)-1])
		if err != nil {
			return s
		}
		if newIdx, ok := seen[n]; ok {
			return fmt.Sprintf("[%d]", newIdx)
		}
		return s
	})
	answer = trailingCiteLineRE.ReplaceAllString(answer, "")
	answer = regexp.MustCompile(`\n{3,}`).ReplaceAllString(answer, "\n\n")
	answer = strings.TrimRight(answer, "\n \u3000")

	usedPositions := make(map[int]bool, len(order))
	for _, n := range order {
		usedPositions[n] = true
	}
	filtered := make([]dto.CitationResponse, 0, len(order))
	for i, c := range citations {
		if usedPositions[i+1] {
			filtered = append(filtered, c)
		}
	}

	return answer, filtered
}
