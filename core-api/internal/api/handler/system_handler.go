package handler

import (
	"database/sql"
	"net/http"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/storage"
)

type SystemHandler struct {
	cfg   config.Config
	store storage.Database
}

func NewSystemHandler(cfg config.Config, store storage.Database) *SystemHandler {
	return &SystemHandler{cfg: cfg, store: store}
}

func (h *SystemHandler) Health(c *gin.Context) {
	dbStatus := "ok"
	if err := h.store.Health(); err != nil {
		dbStatus = "error: " + err.Error()
	}
	c.JSON(http.StatusOK, gin.H{
		"status":   "ok",
		"service":  "core-api",
		"database": dbStatus,
	})
}

// Stats feeds the admin dashboard's chart panel: counts by status so the
// frontend can render simple bar/donut charts without a second round trip.
func (h *SystemHandler) Stats(c *gin.Context) {
	db := h.store.DB()

	var bookCount, chunkCount, sessionCount int64
	_ = db.QueryRow("SELECT COUNT(*) FROM books").Scan(&bookCount)
	_ = db.QueryRow("SELECT COUNT(*) FROM chunks").Scan(&chunkCount)
	_ = db.QueryRow("SELECT COUNT(*) FROM chat_sessions").Scan(&sessionCount)

	c.JSON(http.StatusOK, gin.H{
		"books_total":     bookCount,
		"chunks_total":    chunkCount,
		"sessions_total":  sessionCount,
		"books_by_status": countByStatus(db, "books"),
		"tasks_by_status": countByStatus(db, "tasks"),
	})
}

// Config exposes feature toggles the web-ui needs before rendering nav/routes
// — currently just whether the conversation ("会话") page is enabled.
func (h *SystemHandler) Config(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"chat_enabled": h.cfg.Chat.Enabled})
}

func countByStatus(db *sql.DB, table string) map[string]int64 {
	counts := map[string]int64{}
	rows, err := db.Query("SELECT status, COUNT(*) FROM " + table + " GROUP BY status")
	if err != nil {
		return counts
	}
	defer rows.Close()

	for rows.Next() {
		var status string
		var count int64
		if rows.Scan(&status, &count) == nil {
			counts[status] = count
		}
	}
	return counts
}
