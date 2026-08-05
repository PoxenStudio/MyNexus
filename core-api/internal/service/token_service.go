package service

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/google/uuid"

	"mynexus/core-api/internal/auth"
	"mynexus/core-api/internal/models"
)

type TokenService struct {
	db     *sql.DB
	prefix string
}

func NewTokenService(db *sql.DB, prefix string) *TokenService {
	return &TokenService{db: db, prefix: prefix}
}

// Create generates a new API token and returns it once (raw). Only the hash
// is stored — see docs/系统设计文档.md §8.2.
func (s *TokenService) Create(userID, alias string) (raw string, token *models.APIToken, err error) {
	raw, hash, err := auth.GenerateAPIToken(s.prefix)
	if err != nil {
		return "", nil, err
	}

	suffix := raw
	if len(raw) > 4 {
		suffix = raw[len(raw)-4:]
	}

	token = &models.APIToken{
		ID: uuid.NewString(), UserID: userID, TokenHash: hash, TokenSuffix: suffix, Alias: alias,
		CreatedAt: time.Now().UTC().Format(time.RFC3339),
	}
	_, err = s.db.Exec(
		`INSERT INTO api_tokens (id, user_id, token_hash, token_suffix, alias, is_revoked, created_at) VALUES (?, ?, ?, ?, ?, 0, ?)`,
		token.ID, token.UserID, token.TokenHash, token.TokenSuffix, token.Alias, token.CreatedAt,
	)
	if err != nil {
		return "", nil, fmt.Errorf("insert api token: %w", err)
	}
	return raw, token, nil
}

func (s *TokenService) ListByUser(userID string) ([]models.APIToken, error) {
	rows, err := s.db.Query(
		`SELECT id, user_id, token_hash, token_suffix, alias, COALESCE(last_used_at, ''), COALESCE(expires_at, ''), is_revoked, created_at
		 FROM api_tokens WHERE user_id = ? ORDER BY created_at DESC`, userID)
	if err != nil {
		return nil, fmt.Errorf("list api tokens: %w", err)
	}
	defer rows.Close()

	var tokens []models.APIToken
	for rows.Next() {
		var t models.APIToken
		var revoked int
		if err := rows.Scan(&t.ID, &t.UserID, &t.TokenHash, &t.TokenSuffix, &t.Alias, &t.LastUsedAt, &t.ExpiresAt, &revoked, &t.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan api token: %w", err)
		}
		t.IsRevoked = revoked != 0
		tokens = append(tokens, t)
	}
	return tokens, rows.Err()
}

func (s *TokenService) Revoke(id string) error {
	_, err := s.db.Exec(`UPDATE api_tokens SET is_revoked = 1 WHERE id = ?`, id)
	return err
}

// Authenticate validates a raw token and returns its owning user_id and alias
// (the latter used to label audit log entries as "token:<alias>"), or
// ok=false if it's unknown, revoked, or expired. Touches last_used_at on success.
func (s *TokenService) Authenticate(raw string) (userID, alias string, ok bool) {
	hash := auth.HashToken(raw)
	var id, uid, tokenAlias string
	var revoked int
	var expiresAt sql.NullString
	err := s.db.QueryRow(
		`SELECT id, user_id, alias, is_revoked, expires_at FROM api_tokens WHERE token_hash = ?`, hash,
	).Scan(&id, &uid, &tokenAlias, &revoked, &expiresAt)
	if err != nil || revoked != 0 {
		return "", "", false
	}
	if expiresAt.Valid && expiresAt.String != "" {
		if exp, err := time.Parse(time.RFC3339, expiresAt.String); err == nil && time.Now().After(exp) {
			return "", "", false
		}
	}
	_, _ = s.db.Exec(`UPDATE api_tokens SET last_used_at = ? WHERE id = ?`, time.Now().UTC().Format(time.RFC3339), id)
	return uid, tokenAlias, true
}
