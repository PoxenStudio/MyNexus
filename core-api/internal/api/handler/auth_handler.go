package handler

import (
	"errors"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/auth"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

type AuthHandler struct {
	users     *service.UserService
	sessions  *auth.SessionManager
	audit     *service.AuditService
	uploadDir string
}

func NewAuthHandler(users *service.UserService, sessions *auth.SessionManager, audit *service.AuditService, uploadDir string) *AuthHandler {
	return &AuthHandler{users: users, sessions: sessions, audit: audit, uploadDir: uploadDir}
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

	userID, role, err := h.users.Authenticate(req.Username, req.Password)
	if err != nil {
		_ = h.audit.Log(req.Username, "auth.login_failed", "user", "", "")
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid username or password"})
		return
	}

	sessionID, err := h.sessions.Create(userID, req.Username, role)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	setSessionCookie(c, sessionID)
	_ = h.audit.Log(req.Username, "auth.login", "user", userID, "")
	c.JSON(http.StatusOK, gin.H{"username": req.Username, "role": role})
}

func (h *AuthHandler) Logout(c *gin.Context) {
	if id, err := c.Cookie(auth.SessionCookieName); err == nil {
		h.sessions.Delete(id)
	}
	clearSessionCookie(c)
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "auth.logout", "user", "", "")
	}
	c.Status(http.StatusNoContent)
}

func (h *AuthHandler) Me(c *gin.Context) {
	userID, ok := c.Get("admin_user_id")
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "not logged in"})
		return
	}
	user, err := h.users.GetByID(userID.(string))
	if err != nil || user == nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "not logged in"})
		return
	}
	c.JSON(http.StatusOK, gin.H{
		"username":   user.Username,
		"nickname":   user.Nickname,
		"role":       user.Role,
		"avatar_url": avatarURL(user),
	})
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

	err := h.users.ChangePassword(userID.(string), req.OldPassword, req.NewPassword)
	if errors.Is(err, service.ErrInvalidCredentials) {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "old password is incorrect"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "auth.change_password", "user", userID.(string), "")
	}
	c.Status(http.StatusNoContent)
}

var avatarExts = map[string]bool{".png": true, ".jpg": true, ".jpeg": true, ".webp": true, ".gif": true}

// maxAvatarSize caps the upload well above what any reasonable avatar image
// needs, to avoid an admin (the only caller — this is behind RequireAuth)
// accidentally filling up disk with a huge file.
const maxAvatarSize = 5 << 20 // 5MB

// UploadAvatar stores the image at {uploadDir}/avatars/{admin_id}{ext},
// overwriting any previous avatar for the same admin (single avatar per
// account, no history kept).
func (h *AuthHandler) UploadAvatar(c *gin.Context) {
	userID, ok := c.Get("admin_user_id")
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "not logged in"})
		return
	}

	fileHeader, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "file is required"})
		return
	}
	if fileHeader.Size > maxAvatarSize {
		c.JSON(http.StatusBadRequest, gin.H{"error": "file too large (max 5MB)"})
		return
	}
	ext := strings.ToLower(filepath.Ext(fileHeader.Filename))
	if !avatarExts[ext] {
		c.JSON(http.StatusBadRequest, gin.H{"error": "unsupported image format: " + ext})
		return
	}

	dir := filepath.Join(h.uploadDir, "avatars")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	// Remove any previous avatar under a different extension first, so
	// switching from e.g. .png to .jpg doesn't leave the old file behind.
	removeExistingAvatar(dir, userID.(string))

	relPath := filepath.Join("avatars", userID.(string)+ext)
	if err := c.SaveUploadedFile(fileHeader, filepath.Join(h.uploadDir, relPath)); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if err := h.users.SetAvatar(userID.(string), relPath); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "auth.upload_avatar", "user", userID.(string), "")
	}
	c.JSON(http.StatusOK, gin.H{"avatar_url": avatarPath(userID.(string))})
}

func removeExistingAvatar(dir, userID string) {
	for ext := range avatarExts {
		_ = os.Remove(filepath.Join(dir, userID+ext))
	}
}

// ServeAvatar streams a user's avatar image. Any authenticated caller can
// view any other user's avatar (id isn't a secret) — access control here is
// just "must be logged in".
func (h *AuthHandler) ServeAvatar(c *gin.Context) {
	id := c.Param("id")
	user, err := h.users.GetByID(id)
	if err != nil || user == nil || user.AvatarPath == "" {
		c.Status(http.StatusNotFound)
		return
	}
	// Cache-Control: no-store so the browser re-fetches after a re-upload
	// instead of showing a stale cached image at the same URL.
	c.Header("Cache-Control", "no-store")
	c.File(filepath.Join(h.uploadDir, user.AvatarPath))
}

// avatarURL/avatarPath are relative to apiClient's base URL (which already
// includes "/api/v1" — see web-ui/src/api/client.ts), not the site root.
func avatarURL(user *models.User) string {
	if user.AvatarPath == "" {
		return ""
	}
	return avatarPath(user.ID)
}

func avatarPath(userID string) string {
	return "/auth/avatar/" + userID
}

func setSessionCookie(c *gin.Context, sessionID string) {
	c.SetSameSite(http.SameSiteLaxMode)
	c.SetCookie(auth.SessionCookieName, sessionID, int(auth.SessionTTL.Seconds()), "/", "", false, true)
}

func clearSessionCookie(c *gin.Context) {
	c.SetSameSite(http.SameSiteLaxMode)
	c.SetCookie(auth.SessionCookieName, "", -1, "/", "", false, true)
}
