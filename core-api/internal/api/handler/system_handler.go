package handler

import (
	"database/sql"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/service"
	"mynexus/core-api/internal/storage"
)

type SystemHandler struct {
	cfg    config.Config
	store  storage.Database
	worker *coordinator.WorkerClient
	audit  *service.AuditService
}

func NewSystemHandler(cfg config.Config, store storage.Database, worker *coordinator.WorkerClient, audit *service.AuditService) *SystemHandler {
	return &SystemHandler{cfg: cfg, store: store, worker: worker, audit: audit}
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

// Settings returns every config.yaml section the system settings page can
// edit (everything except server/auth — see dto.SystemSettings), read fresh
// from disk rather than the in-memory h.cfg so it reflects any change made
// since this process started (e.g. a hand-edit, or another admin's save).
func (h *SystemHandler) Settings(c *gin.Context) {
	cfg, err := config.LoadFromFile()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, dto.SystemSettings{
		Storage: cfg.Storage, Worker: cfg.Worker, Embedding: cfg.Embedding,
		LLM: cfg.LLM, Splitter: cfg.Splitter, I18n: cfg.I18n, Chat: cfg.Chat,
		Keyword: cfg.Keyword, Debug: cfg.Debug, Summary: cfg.Summary,
	})
}

// SaveSettings rewrites config.yaml with the submitted sections, leaving
// server/auth exactly as currently on disk (re-read fresh, not from h.cfg,
// so an env-injected secret never gets baked into the file — see
// config.LoadFromFile). It then restarts both services: Worker via a
// best-effort gRPC Shutdown call, and this process via os.Exit after the
// response is flushed — see the proto comment on WorkerService.Shutdown and
// docs/部署说明.md for what "restart" does and doesn't do in each deployment
// mode.
func (h *SystemHandler) SaveSettings(c *gin.Context) {
	var body dto.SystemSettings
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	onDisk, err := config.LoadFromFile()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "read current config: " + err.Error()})
		return
	}

	onDisk.Storage = body.Storage
	onDisk.Worker = body.Worker
	onDisk.Embedding = body.Embedding
	onDisk.LLM = body.LLM
	onDisk.Splitter = body.Splitter
	onDisk.I18n = body.I18n
	onDisk.Chat = body.Chat
	onDisk.Keyword = body.Keyword
	onDisk.Debug = body.Debug
	onDisk.Summary = body.Summary

	if err := config.SaveToFile(onDisk); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "write config: " + err.Error()})
		return
	}

	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "system.save_settings", "system_settings", "", "")
	}

	c.JSON(http.StatusOK, gin.H{"restarting": true})

	// Best-effort: Worker may be down already, or may not come back up on its
	// own in a supervisor-less dev run — either way this request has already
	// succeeded from the caller's point of view.
	go func() { _ = h.worker.Shutdown() }()

	// Give the response above time to actually reach the client before this
	// process exits.
	go func() {
		time.Sleep(300 * time.Millisecond)
		os.Exit(0)
	}()
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
