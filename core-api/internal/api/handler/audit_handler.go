package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/service"
)

type AuditHandler struct {
	audit *service.AuditService
}

func NewAuditHandler(audit *service.AuditService) *AuditHandler {
	return &AuditHandler{audit: audit}
}

func (h *AuditHandler) List(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	size, _ := strconv.Atoi(c.DefaultQuery("size", "20"))

	entries, total, err := h.audit.List(page, size)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	items := make([]dto.AuditLogResponse, 0, len(entries))
	for _, e := range entries {
		items = append(items, dto.NewAuditLogResponse(e))
	}
	c.JSON(http.StatusOK, dto.AuditLogListResponse{Items: items, Total: total, Page: page, Size: size})
}
