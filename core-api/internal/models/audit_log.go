package models

type AuditLogEntry struct {
	ID         string
	Actor      string
	Action     string
	TargetType string
	TargetID   string
	Detail     string
	CreatedAt  string
}
