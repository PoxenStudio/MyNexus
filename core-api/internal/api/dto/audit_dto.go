package dto

import "mynexus/core-api/internal/models"

type AuditLogResponse struct {
	ID         string `json:"id"`
	Actor      string `json:"actor"`
	Action     string `json:"action"`
	TargetType string `json:"target_type"`
	TargetID   string `json:"target_id"`
	Detail     string `json:"detail"`
	CreatedAt  string `json:"created_at"`
}

func NewAuditLogResponse(e models.AuditLogEntry) AuditLogResponse {
	return AuditLogResponse{
		ID: e.ID, Actor: e.Actor, Action: e.Action, TargetType: e.TargetType,
		TargetID: e.TargetID, Detail: e.Detail, CreatedAt: e.CreatedAt,
	}
}

type AuditLogListResponse struct {
	Items []AuditLogResponse `json:"items"`
	Total int64              `json:"total"`
	Page  int                `json:"page"`
	Size  int                `json:"size"`
}
