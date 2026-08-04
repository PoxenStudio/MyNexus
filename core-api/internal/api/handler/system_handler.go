package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/storage/sqlite"
)

type SystemHandler struct {
	cfg   config.Config
	store *sqlite.Store
}

func NewSystemHandler(cfg config.Config, store *sqlite.Store) *SystemHandler {
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

func (h *SystemHandler) Stats(c *gin.Context) {
	var bookCount int64
	_ = h.store.DB().QueryRow("SELECT COUNT(*) FROM books").Scan(&bookCount)

	c.JSON(http.StatusOK, gin.H{
		"books": bookCount,
		"mode":  "m1-skeleton",
	})
}
