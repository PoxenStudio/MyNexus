-- Mirrors storage/sqlite/migrations/0007_user_roles.sql — see that file for
-- the full rationale.

ALTER TABLE admin_users RENAME TO users;

ALTER TABLE users ADD COLUMN nickname TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'admin';
ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP;
