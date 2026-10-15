package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/service"
)

// LLMUsageHandler exposes the HTTP endpoints the web-ui's book-detail token
// card and dashboard token chart hit — see core-api/internal/service/llm_usage_service.go
// for the actual queries; this handler is just request parsing + JSON shaping.
type LLMUsageHandler struct {
	llmUsage *service.LLMUsageService
}

func NewLLMUsageHandler(llmUsage *service.LLMUsageService) *LLMUsageHandler {
	return &LLMUsageHandler{llmUsage: llmUsage}
}

// BookTokenUsage is the aggregate + per-call-site breakdown the book-detail
// card renders. One book, one GET.
func (h *LLMUsageHandler) BookTokenUsage(c *gin.Context) {
	bookID := c.Param("id")
	if bookID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "book id required"})
		return
	}
	total, prompt, completion, calls, err := h.llmUsage.SumByBook(bookID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	breakdown, err := h.llmUsage.CallSiteBreakdown(bookID, 50)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{
		"book_id":          bookID,
		"total_tokens":     total,
		"prompt_tokens":    prompt,
		"completion_tokens": completion,
		"calls":            calls,
		"breakdown":        breakdown,
	})
}

// TokenStats backs the dashboard折线图 and饼图 — returns daily totals grouped
// by llm_provider over a rolling window (rangeDays, default 7). Callers send
// ?range=1|7|30; anything else we clamp to 30 so a typo can't produce a full
// history dump by accident.
func (h *LLMUsageHandler) TokenStats(c *gin.Context) {
	rangeDays := 7
	if v := c.Query("range"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 && n <= 365 {
			rangeDays = n
		}
	}
	rows, err := h.llmUsage.DailyByProvider(rangeDays)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Aggregate today's totals per provider for the pie chart.
	today := gin.H{}
	for _, r := range rows {
		if _, seen := today[r.LLMProvider]; !seen {
			today[r.LLMProvider] = 0
		}
		today[r.LLMProvider] = today[r.LLMProvider].(int) + r.TotalTokens
	}

	c.JSON(http.StatusOK, gin.H{
		"range_days":   rangeDays,
		"daily":        rows,
		"today_by_provider": today,
	})
}
