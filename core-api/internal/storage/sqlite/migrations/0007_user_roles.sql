-- Turns the admin-only login table into a general user table: renames
-- admin_users -> users, and adds the columns needed for multi-user support
-- (nickname, role, status, last_login_at). Existing rows (today just the
-- seeded default account) become role='admin', status='active' via the
-- column defaults below, so no data backfill is required.
--
-- See .claude/memory/mynexus_admin_auth.md for why the table existed in the
-- first place, and docs/需求文档.md for the user-management requirement that
-- prompted this migration.

ALTER TABLE admin_users RENAME TO users;

ALTER TABLE users ADD COLUMN nickname TEXT NOT NULL DEFAULT '';
-- role: 'admin' (full backend access) | 'user' (chat + own profile only).
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'admin';
-- status: 'active' | 'disabled'. Disabled accounts can no longer log in, but
-- an already-issued session is left to expire naturally (SessionTTL, 24h)
-- rather than being force-invalidated — see mynexus_user_management.md.
ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE users ADD COLUMN last_login_at TEXT;
