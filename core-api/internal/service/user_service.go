package service

import (
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"mynexus/core-api/internal/auth"
	"mynexus/core-api/internal/models"
)

const DefaultAdminUsername = "admin"
const DefaultAdminPassword = "admin"

var ErrInvalidCredentials = errors.New("invalid username or password")
var ErrUsernameTaken = errors.New("username already exists")
var ErrLastAdmin = errors.New("cannot demote or disable the last remaining admin")
var ErrUserNotFound = errors.New("user not found")

type UserService struct {
	db *sql.DB
}

func NewUserService(db *sql.DB) *UserService {
	return &UserService{db: db}
}

// EnsureDefaultAdmin seeds the admin/admin account the first time the users
// table is empty. Idempotent — safe to call on every startup.
func (s *UserService) EnsureDefaultAdmin() error {
	var count int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM users`).Scan(&count); err != nil {
		return fmt.Errorf("count users: %w", err)
	}
	if count > 0 {
		return nil
	}

	hash, err := auth.HashPassword(DefaultAdminPassword)
	if err != nil {
		return fmt.Errorf("hash default admin password: %w", err)
	}
	now := time.Now().UTC().Format(time.RFC3339)
	_, err = s.db.Exec(
		`INSERT INTO users (id, username, nickname, password_hash, role, status, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		uuid.NewString(), DefaultAdminUsername, "", hash, models.RoleAdmin, models.StatusActive, now, now,
	)
	if err != nil {
		return fmt.Errorf("insert default admin: %w", err)
	}
	return nil
}

// Authenticate returns the user's (ID, role) on a matching username/password
// for an active account, or ErrInvalidCredentials otherwise. Deliberately
// doesn't distinguish "unknown user", "wrong password", or "disabled account"
// in the returned error, to avoid leaking which usernames exist or are locked
// out. On success it also stamps last_login_at.
func (s *UserService) Authenticate(username, password string) (id, role string, err error) {
	var hash, status string
	err = s.db.QueryRow(`SELECT id, password_hash, role, status FROM users WHERE username = ?`, username).
		Scan(&id, &hash, &role, &status)
	if err == sql.ErrNoRows {
		return "", "", ErrInvalidCredentials
	}
	if err != nil {
		return "", "", fmt.Errorf("lookup user: %w", err)
	}
	if status != models.StatusActive {
		return "", "", ErrInvalidCredentials
	}
	if !auth.CheckPassword(hash, password) {
		return "", "", ErrInvalidCredentials
	}

	now := time.Now().UTC().Format(time.RFC3339)
	if _, err := s.db.Exec(`UPDATE users SET last_login_at = ? WHERE id = ?`, now, id); err != nil {
		return "", "", fmt.Errorf("stamp last_login_at: %w", err)
	}
	return id, role, nil
}

func (s *UserService) GetByID(id string) (*models.User, error) {
	return s.scanOne(`SELECT id, username, nickname, password_hash, role, status,
		avatar_path, COALESCE(last_login_at, ''), created_at, updated_at FROM users WHERE id = ?`, id)
}

func (s *UserService) List() ([]models.User, error) {
	rows, err := s.db.Query(`SELECT id, username, nickname, password_hash, role, status,
		avatar_path, COALESCE(last_login_at, ''), created_at, updated_at FROM users ORDER BY created_at ASC`)
	if err != nil {
		return nil, fmt.Errorf("list users: %w", err)
	}
	defer rows.Close()

	var out []models.User
	for rows.Next() {
		var u models.User
		if err := rows.Scan(&u.ID, &u.Username, &u.Nickname, &u.PasswordHash, &u.Role, &u.Status,
			&u.AvatarPath, &u.LastLoginAt, &u.CreatedAt, &u.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan user: %w", err)
		}
		out = append(out, u)
	}
	return out, rows.Err()
}

// Create adds a new login account. role must be models.RoleAdmin or
// models.RoleUser (validated by the caller/handler).
func (s *UserService) Create(username, nickname, password, role string) (*models.User, error) {
	var exists int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM users WHERE username = ?`, username).Scan(&exists); err != nil {
		return nil, fmt.Errorf("check username: %w", err)
	}
	if exists > 0 {
		return nil, ErrUsernameTaken
	}

	hash, err := auth.HashPassword(password)
	if err != nil {
		return nil, fmt.Errorf("hash password: %w", err)
	}
	id := uuid.NewString()
	now := time.Now().UTC().Format(time.RFC3339)
	_, err = s.db.Exec(
		`INSERT INTO users (id, username, nickname, password_hash, role, status, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		id, username, nickname, hash, role, models.StatusActive, now, now,
	)
	if err != nil {
		return nil, fmt.Errorf("insert user: %w", err)
	}
	return s.GetByID(id)
}

// SetRole changes a user's role. Refuses to demote the last remaining admin
// account, so an operator can never lock themselves (or everyone) out of the
// admin backend entirely.
func (s *UserService) SetRole(id, role string) error {
	u, err := s.GetByID(id)
	if err != nil {
		return err
	}
	if u == nil {
		return ErrUserNotFound
	}
	if u.Role == models.RoleAdmin && role != models.RoleAdmin {
		if err := s.requireNotLastAdmin(id); err != nil {
			return err
		}
	}
	_, err = s.db.Exec(`UPDATE users SET role = ?, updated_at = ? WHERE id = ?`,
		role, time.Now().UTC().Format(time.RFC3339), id)
	return err
}

// SetStatus enables/disables an account. Refuses to disable the last
// remaining active admin account, for the same reason as SetRole.
func (s *UserService) SetStatus(id, status string) error {
	u, err := s.GetByID(id)
	if err != nil {
		return err
	}
	if u == nil {
		return ErrUserNotFound
	}
	if u.Role == models.RoleAdmin && status != models.StatusActive {
		if err := s.requireNotLastAdmin(id); err != nil {
			return err
		}
	}
	_, err = s.db.Exec(`UPDATE users SET status = ?, updated_at = ? WHERE id = ?`,
		status, time.Now().UTC().Format(time.RFC3339), id)
	return err
}

// requireNotLastAdmin returns ErrLastAdmin if id is the only active admin.
func (s *UserService) requireNotLastAdmin(id string) error {
	var count int
	err := s.db.QueryRow(
		`SELECT COUNT(*) FROM users WHERE role = ? AND status = ? AND id != ?`,
		models.RoleAdmin, models.StatusActive, id,
	).Scan(&count)
	if err != nil {
		return fmt.Errorf("count other admins: %w", err)
	}
	if count == 0 {
		return ErrLastAdmin
	}
	return nil
}

// AdminResetPassword lets an admin set another user's password directly, no
// old-password check (that's ChangePassword, for self-service).
func (s *UserService) AdminResetPassword(id, newPassword string) error {
	hash, err := auth.HashPassword(newPassword)
	if err != nil {
		return fmt.Errorf("hash new password: %w", err)
	}
	res, err := s.db.Exec(`UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?`,
		hash, time.Now().UTC().Format(time.RFC3339), id)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return ErrUserNotFound
	}
	return nil
}

// SetAvatar records the on-disk path (relative to storage.upload_dir) of the
// user's uploaded avatar image.
func (s *UserService) SetAvatar(userID, avatarPath string) error {
	_, err := s.db.Exec(
		`UPDATE users SET avatar_path = ?, updated_at = ? WHERE id = ?`,
		avatarPath, time.Now().UTC().Format(time.RFC3339), userID,
	)
	return err
}

// SetNickname lets a user update their own display name.
func (s *UserService) SetNickname(userID, nickname string) error {
	_, err := s.db.Exec(
		`UPDATE users SET nickname = ?, updated_at = ? WHERE id = ?`,
		nickname, time.Now().UTC().Format(time.RFC3339), userID,
	)
	return err
}

// ChangePassword verifies oldPassword against the stored hash before setting
// newPassword, so a stolen session cookie alone can't take over the account.
func (s *UserService) ChangePassword(userID, oldPassword, newPassword string) error {
	u, err := s.GetByID(userID)
	if err != nil {
		return err
	}
	if u == nil {
		return ErrInvalidCredentials
	}
	if !auth.CheckPassword(u.PasswordHash, oldPassword) {
		return ErrInvalidCredentials
	}

	newHash, err := auth.HashPassword(newPassword)
	if err != nil {
		return fmt.Errorf("hash new password: %w", err)
	}
	_, err = s.db.Exec(
		`UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?`,
		newHash, time.Now().UTC().Format(time.RFC3339), userID,
	)
	return err
}

func (s *UserService) scanOne(query string, args ...any) (*models.User, error) {
	var u models.User
	err := s.db.QueryRow(query, args...).Scan(&u.ID, &u.Username, &u.Nickname, &u.PasswordHash, &u.Role, &u.Status,
		&u.AvatarPath, &u.LastLoginAt, &u.CreatedAt, &u.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("get user: %w", err)
	}
	return &u, nil
}
