-- Mirrors storage/sqlite/migrations/0004_admin_avatar.sql.

ALTER TABLE admin_users ADD COLUMN avatar_path TEXT NOT NULL DEFAULT '';
