package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/service"
)

type TokenHandler struct {
	tokens *service.TokenService
	audit  *service.AuditService
}

func NewTokenHandler(tokens *service.TokenService, audit *service.AuditService) *TokenHandler {
	return &TokenHandler{tokens: tokens, audit: audit}
}

func (h *TokenHandler) Create(c *gin.Context) {
	var req dto.CreateTokenRequest
	_ = c.ShouldBindJSON(&req)

	raw, token, err := h.tokens.Create(defaultUserID, req.Alias)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "token.create", "api_token", token.ID, "alias="+token.Alias)
	}
	c.JSON(http.StatusCreated, dto.CreateTokenResponse{ID: token.ID, Token: raw, Alias: token.Alias})
}

func (h *TokenHandler) List(c *gin.Context) {
	tokens, err := h.tokens.ListByUser(defaultUserID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	items := make([]dto.TokenResponse, 0, len(tokens))
	for _, t := range tokens {
		items = append(items, dto.NewTokenResponse(t))
	}
	c.JSON(http.StatusOK, dto.TokenListResponse{Items: items})
}

func (h *TokenHandler) Revoke(c *gin.Context) {
	id := c.Param("id")
	if err := h.tokens.Revoke(id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "token.revoke", "api_token", id, "")
	}
	c.Status(http.StatusNoContent)
}
