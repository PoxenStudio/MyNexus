package models

const (
	RoleAdmin = "admin"
	RoleUser  = "user"

	StatusActive   = "active"
	StatusDisabled = "disabled"
)

// User is a login account for the web-ui. "admin" role accounts get the full
// backend (dashboard, books, tasks, tokens, audit log, user management);
// "user" role accounts only get the chat page and their own profile — see
// middleware.RequireAdmin and the frontend router guard.
type User struct {
	ID           string
	Username     string
	Nickname     string
	PasswordHash string
	Role         string
	Status       string
	// AvatarPath is relative to storage.upload_dir; empty means no custom
	// avatar uploaded (see UserService.SetAvatar).
	AvatarPath  string
	LastLoginAt string // empty means never logged in
	CreatedAt   string
	UpdatedAt   string
}
