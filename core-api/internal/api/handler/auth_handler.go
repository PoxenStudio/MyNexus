package handler

import (
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/auth"
	"mynexus/core-api/internal/service"
)

type AuthHandler struct {
	admins   *service.AdminUserService
	sessions *auth.SessionManager
	audit    *service.AuditService
}

func NewAuthHandler(admins *service.AdminUserService, sessions *auth.SessionManager, audit *service.AuditService) *AuthHandler {
	return &AuthHandler{admins: admins, sessions: sessions, audit: audit}
}

type loginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

func (h *AuthHandler) Login(c *gin.Context) {
	var req loginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "username and password are required"})
		return
	}

	userID, err := h.admins.Authenticate(req.Username, req.Password)
	if err != nil {
		_ = h.audit.Log(req.Username, "auth.login_failed", "admin_user", "", "")
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid username or password"})
		return
	}

	sessionID, err := h.sessions.Create(userID, req.Username)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	setSessionCookie(c, sessionID)
	_ = h.audit.Log(req.Username, "auth.login", "admin_user", userID, "")
	c.JSON(http.StatusOK, gin.H{"username": req.Username})
}

func (h *AuthHandler) Logout(c *gin.Context) {
	if id, err := c.Cookie(auth.SessionCookieName); err == nil {
		h.sessions.Delete(id)
	}
	clearSessionCookie(c)
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "auth.logout", "admin_user", "", "")
	}
	c.Status(http.StatusNoContent)
}

func (h *AuthHandler) Me(c *gin.Context) {
	userID, ok := c.Get("admin_user_id")
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "not logged in"})
		return
	}
	user, err := h.admins.GetByID(userID.(string))
	if err != nil || user == nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "not logged in"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"username": user.Username})
}

type changePasswordRequest struct {
	OldPassword string `json:"old_password" binding:"required"`
	NewPassword string `json:"new_password" binding:"required"`
}

func (h *AuthHandler) ChangePassword(c *gin.Context) {
	userID, ok := c.Get("admin_user_id")
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "not logged in"})
		return
	}

	var req changePasswordRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "old_password and new_password are required"})
		return
	}
	if len(req.NewPassword) < 4 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "new password must be at least 4 characters"})
		return
	}

	err := h.admins.ChangePassword(userID.(string), req.OldPassword, req.NewPassword)
	if errors.Is(err, service.ErrInvalidCredentials) {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "old password is incorrect"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "auth.change_password", "admin_user", userID.(string), "")
	}
	c.Status(http.StatusNoContent)
}

func setSessionCookie(c *gin.Context, sessionID string) {
	c.SetSameSite(http.SameSiteLaxMode)
	c.SetCookie(auth.SessionCookieName, sessionID, int(auth.SessionTTL.Seconds()), "/", "", false, true)
}

func clearSessionCookie(c *gin.Context) {
	c.SetSameSite(http.SameSiteLaxMode)
	c.SetCookie(auth.SessionCookieName, "", -1, "/", "", false, true)
}
