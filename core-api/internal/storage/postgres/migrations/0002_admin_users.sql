-- Mirrors storage/sqlite/migrations/0002_admin_users.sql — only DATETIME -> TIMESTAMP differs.

CREATE TABLE IF NOT EXISTS admin_users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
