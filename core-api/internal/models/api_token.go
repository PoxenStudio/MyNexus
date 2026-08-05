package models

type APIToken struct {
	ID          string
	UserID      string
	TokenHash   string
	TokenSuffix string
	Alias       string
	LastUsedAt  string
	ExpiresAt   string
	IsRevoked   bool
	CreatedAt   string
}
