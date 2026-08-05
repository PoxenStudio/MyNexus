package service

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/google/uuid"

	"mynexus/core-api/internal/models"
)

type AuditService struct {
	db *sql.DB
}

func NewAuditService(db *sql.DB) *AuditService {
	return &AuditService{db: db}
}

// Log records one admin action. Errors are the caller's to decide on — most
// call sites treat audit logging as best-effort (log and continue) so a
// logging hiccup never blocks the actual operation from succeeding.
func (s *AuditService) Log(actor, action, targetType, targetID, detail string) error {
	_, err := s.db.Exec(
		`INSERT INTO admin_audit_log (id, actor, action, target_type, target_id, detail, created_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?)`,
		uuid.NewString(), actor, action, targetType, targetID, detail, time.Now().UTC().Format(time.RFC3339),
	)
	if err != nil {
		return fmt.Errorf("insert audit log: %w", err)
	}
	return nil
}

func (s *AuditService) List(page, size int) ([]models.AuditLogEntry, int64, error) {
	if page < 1 {
		page = 1
	}
	if size < 1 || size > 200 {
		size = 20
	}

	var total int64
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM admin_audit_log`).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count audit log: %w", err)
	}

	rows, err := s.db.Query(
		`SELECT id, actor, action, target_type, target_id, detail, created_at
		 FROM admin_audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?`,
		size, (page-1)*size,
	)
	if err != nil {
		return nil, 0, fmt.Errorf("list audit log: %w", err)
	}
	defer rows.Close()

	var entries []models.AuditLogEntry
	for rows.Next() {
		var e models.AuditLogEntry
		if err := rows.Scan(&e.ID, &e.Actor, &e.Action, &e.TargetType, &e.TargetID, &e.Detail, &e.CreatedAt); err != nil {
			return nil, 0, fmt.Errorf("scan audit log: %w", err)
		}
		entries = append(entries, e)
	}
	return entries, total, rows.Err()
}
