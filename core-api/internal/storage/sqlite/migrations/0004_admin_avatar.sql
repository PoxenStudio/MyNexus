-- Admin account avatar: path to the uploaded image file on disk, relative to
-- storage.upload_dir (see AdminUserService.SetAvatar) — empty means "no
-- custom avatar, show the default".

ALTER TABLE admin_users ADD COLUMN avatar_path TEXT NOT NULL DEFAULT '';
