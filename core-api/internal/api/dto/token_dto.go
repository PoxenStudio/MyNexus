package dto

import "mynexus/core-api/internal/models"

type CreateTokenRequest struct {
	Alias string `json:"alias"`
}

// CreateTokenResponse is the only place the full raw token is ever returned.
type CreateTokenResponse struct {
	ID    string `json:"id"`
	Token string `json:"token"`
	Alias string `json:"alias"`
}

type TokenResponse struct {
	ID          string `json:"id"`
	Alias       string `json:"alias"`
	MaskedToken string `json:"masked_token"`
	LastUsedAt  string `json:"last_used_at"`
	IsRevoked   bool   `json:"is_revoked"`
	CreatedAt   string `json:"created_at"`
}

func NewTokenResponse(t models.APIToken) TokenResponse {
	masked := "••••••••" + t.TokenSuffix
	return TokenResponse{
		ID: t.ID, Alias: t.Alias, MaskedToken: masked,
		LastUsedAt: t.LastUsedAt, IsRevoked: t.IsRevoked, CreatedAt: t.CreatedAt,
	}
}

type TokenListResponse struct {
	Items []TokenResponse `json:"items"`
}
