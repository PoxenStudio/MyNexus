package handler

import (
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

// UserHandler implements the "用户管理" admin page: list/create accounts,
// change role, enable/disable, and reset another user's password. All routes
// are behind middleware.RequireAdmin (see router.go) — a plain "user" role
// account never reaches these.
type UserHandler struct {
	users *service.UserService
	audit *service.AuditService
}

func NewUserHandler(users *service.UserService, audit *service.AuditService) *UserHandler {
	return &UserHandler{users: users, audit: audit}
}

type userDTO struct {
	ID          string `json:"id"`
	Username    string `json:"username"`
	Nickname    string `json:"nickname"`
	Role        string `json:"role"`
	Status      string `json:"status"`
	AvatarURL   string `json:"avatar_url"`
	LastLoginAt string `json:"last_login_at"`
	CreatedAt   string `json:"created_at"`
}

func toUserDTO(u models.User) userDTO {
	avatar := ""
	if u.AvatarPath != "" {
		avatar = avatarPath(u.ID)
	}
	return userDTO{
		ID: u.ID, Username: u.Username, Nickname: u.Nickname, Role: u.Role, Status: u.Status,
		AvatarURL: avatar, LastLoginAt: u.LastLoginAt, CreatedAt: u.CreatedAt,
	}
}

func (h *UserHandler) List(c *gin.Context) {
	users, err := h.users.List()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	out := make([]userDTO, 0, len(users))
	for _, u := range users {
		out = append(out, toUserDTO(u))
	}
	c.JSON(http.StatusOK, gin.H{"users": out})
}

type createUserRequest struct {
	Username string `json:"username" binding:"required"`
	Nickname string `json:"nickname"`
	Password string `json:"password" binding:"required"`
	Role     string `json:"role" binding:"required"`
}

func (h *UserHandler) Create(c *gin.Context) {
	var req createUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "username, password and role are required"})
		return
	}
	if req.Role != models.RoleAdmin && req.Role != models.RoleUser {
		c.JSON(http.StatusBadRequest, gin.H{"error": "role must be 'admin' or 'user'"})
		return
	}
	if len(req.Password) < 4 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "password must be at least 4 characters"})
		return
	}

	user, err := h.users.Create(req.Username, req.Nickname, req.Password, req.Role)
	if errors.Is(err, service.ErrUsernameTaken) {
		c.JSON(http.StatusConflict, gin.H{"error": "username already exists"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "user.create", "user", user.ID, "")
	}
	c.JSON(http.StatusCreated, toUserDTO(*user))
}

type setRoleRequest struct {
	Role string `json:"role" binding:"required"`
}

func (h *UserHandler) SetRole(c *gin.Context) {
	id := c.Param("id")
	var req setRoleRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "role is required"})
		return
	}
	if req.Role != models.RoleAdmin && req.Role != models.RoleUser {
		c.JSON(http.StatusBadRequest, gin.H{"error": "role must be 'admin' or 'user'"})
		return
	}
	if selfID, ok := c.Get("admin_user_id"); ok && selfID.(string) == id && req.Role != models.RoleAdmin {
		c.JSON(http.StatusBadRequest, gin.H{"error": "cannot change your own role"})
		return
	}

	err := h.users.SetRole(id, req.Role)
	if h.handleUserErr(c, err) {
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "user.set_role", "user", id, req.Role)
	}
	c.Status(http.StatusNoContent)
}

type setStatusRequest struct {
	Status string `json:"status" binding:"required"`
}

func (h *UserHandler) SetStatus(c *gin.Context) {
	id := c.Param("id")
	var req setStatusRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "status is required"})
		return
	}
	if req.Status != models.StatusActive && req.Status != models.StatusDisabled {
		c.JSON(http.StatusBadRequest, gin.H{"error": "status must be 'active' or 'disabled'"})
		return
	}
	if selfID, ok := c.Get("admin_user_id"); ok && selfID.(string) == id && req.Status != models.StatusActive {
		c.JSON(http.StatusBadRequest, gin.H{"error": "cannot disable your own account"})
		return
	}

	err := h.users.SetStatus(id, req.Status)
	if h.handleUserErr(c, err) {
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "user.set_status", "user", id, req.Status)
	}
	c.Status(http.StatusNoContent)
}

type resetPasswordRequest struct {
	NewPassword string `json:"new_password" binding:"required"`
}

func (h *UserHandler) ResetPassword(c *gin.Context) {
	id := c.Param("id")
	var req resetPasswordRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "new_password is required"})
		return
	}
	if len(req.NewPassword) < 4 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "new password must be at least 4 characters"})
		return
	}

	err := h.users.AdminResetPassword(id, req.NewPassword)
	if h.handleUserErr(c, err) {
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "user.reset_password", "user", id, "")
	}
	c.Status(http.StatusNoContent)
}

// handleUserErr writes the right status code for a service-layer error and
// reports whether it wrote a response (true = caller should return).
func (h *UserHandler) handleUserErr(c *gin.Context, err error) bool {
	switch {
	case err == nil:
		return false
	case errors.Is(err, service.ErrUserNotFound):
		c.JSON(http.StatusNotFound, gin.H{"error": "user not found"})
	case errors.Is(err, service.ErrLastAdmin):
		c.JSON(http.StatusBadRequest, gin.H{"error": "cannot demote or disable the last remaining admin"})
	default:
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	}
	return true
}
