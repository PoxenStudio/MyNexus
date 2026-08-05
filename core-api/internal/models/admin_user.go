package models

type AdminUser struct {
	ID           string
	Username     string
	PasswordHash string
	// AvatarPath is relative to storage.upload_dir; empty means no custom
	// avatar uploaded (see AdminUserService.SetAvatar).
	AvatarPath string
	CreatedAt  string
	UpdatedAt  string
}
