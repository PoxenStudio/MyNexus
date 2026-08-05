-- Admin login accounts for the web-ui backend (session-based, not API tokens
-- — see docs/系统设计文档.md and .claude/memory/mynexus_migration_versioning.md).
-- The default admin/admin account is seeded in Go (AdminUserService.EnsureDefaultAdmin),
-- not here, since the password must be bcrypt-hashed before insert.

CREATE TABLE IF NOT EXISTS admin_users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
