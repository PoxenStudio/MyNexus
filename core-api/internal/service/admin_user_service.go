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

type AdminUserService struct {
	db *sql.DB
}

func NewAdminUserService(db *sql.DB) *AdminUserService {
	return &AdminUserService{db: db}
}

// EnsureDefaultAdmin seeds the admin/admin account the first time the
// admin_users table is empty. Idempotent — safe to call on every startup.
func (s *AdminUserService) EnsureDefaultAdmin() error {
	var count int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM admin_users`).Scan(&count); err != nil {
		return fmt.Errorf("count admin users: %w", err)
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
		`INSERT INTO admin_users (id, username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)`,
		uuid.NewString(), DefaultAdminUsername, hash, now, now,
	)
	if err != nil {
		return fmt.Errorf("insert default admin: %w", err)
	}
	return nil
}

// Authenticate returns the user's ID on a matching username/password, or
// ErrInvalidCredentials otherwise. Deliberately doesn't distinguish "unknown
// user" from "wrong password" in the returned error, to avoid leaking which
// usernames exist.
func (s *AdminUserService) Authenticate(username, password string) (string, error) {
	var id, hash string
	err := s.db.QueryRow(`SELECT id, password_hash FROM admin_users WHERE username = ?`, username).Scan(&id, &hash)
	if err == sql.ErrNoRows {
		return "", ErrInvalidCredentials
	}
	if err != nil {
		return "", fmt.Errorf("lookup admin user: %w", err)
	}
	if !auth.CheckPassword(hash, password) {
		return "", ErrInvalidCredentials
	}
	return id, nil
}

func (s *AdminUserService) GetByID(id string) (*models.AdminUser, error) {
	var u models.AdminUser
	err := s.db.QueryRow(
		`SELECT id, username, password_hash, created_at, updated_at FROM admin_users WHERE id = ?`, id,
	).Scan(&u.ID, &u.Username, &u.PasswordHash, &u.CreatedAt, &u.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("get admin user: %w", err)
	}
	return &u, nil
}

// ChangePassword verifies oldPassword against the stored hash before setting
// newPassword, so a stolen session cookie alone can't take over the account.
func (s *AdminUserService) ChangePassword(userID, oldPassword, newPassword string) error {
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
		`UPDATE admin_users SET password_hash = ?, updated_at = ? WHERE id = ?`,
		newHash, time.Now().UTC().Format(time.RFC3339), userID,
	)
	return err
}
