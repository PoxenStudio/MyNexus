-- Initial schema — consolidates 0001 through 0016 into one file.
-- Dev-only: rebuild postgres DB from scratch on each startup.
-- Mirrors storage/sqlite/migrations/0001_init.sql (DATETIME -> TIMESTAMP).

CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    avatar_path    TEXT NOT NULL DEFAULT '',
    nickname       TEXT NOT NULL DEFAULT '',
    role           TEXT NOT NULL DEFAULT 'admin',
    status         TEXT NOT NULL DEFAULT 'active',
    last_login_at  TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id          TEXT PRIMARY KEY,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    target_type TEXT DEFAULT '',
    target_id   TEXT DEFAULT '',
    detail      TEXT DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON admin_audit_log(created_at);

CREATE TABLE IF NOT EXISTS books (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    title           TEXT NOT NULL DEFAULT '',
    author          TEXT DEFAULT '',
    publisher       TEXT DEFAULT '',
    language        TEXT DEFAULT '',
    publish_date    TEXT DEFAULT '',
    isbn            TEXT DEFAULT '',
    source_origin   TEXT NOT NULL DEFAULT 'DirectUpload',
    source_format   TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    tags            TEXT DEFAULT '[]',
    category        TEXT DEFAULT '',
    summary         TEXT NOT NULL DEFAULT '',
    keywords        TEXT NOT NULL DEFAULT '[]',
    cover_path      TEXT NOT NULL DEFAULT '',
    mybooks_id      INTEGER DEFAULT NULL,
    reading_guide   TEXT NOT NULL DEFAULT '',
    reference_index TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chapters (
    id           TEXT PRIMARY KEY,
    book_id      TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    title        TEXT NOT NULL DEFAULT '',
    level        INTEGER NOT NULL DEFAULT 1,
    sort_order   INTEGER NOT NULL DEFAULT 0,
    content      TEXT DEFAULT '',
    summary      TEXT DEFAULT '',
    keywords     TEXT NOT NULL DEFAULT '[]',
    definitions  TEXT NOT NULL DEFAULT '[]',
    "references" TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_chapters_book ON chapters(book_id);

CREATE TABLE IF NOT EXISTS chunks (
    id           TEXT PRIMARY KEY,
    chapter_id   TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    book_id      TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    content      TEXT NOT NULL,
    token_count  INTEGER NOT NULL DEFAULT 0,
    position     INTEGER NOT NULL DEFAULT 0,
    vector_id    TEXT DEFAULT '',
    keywords     TEXT DEFAULT '[]',
    start_offset INTEGER NOT NULL DEFAULT 0,
    end_offset   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_chunks_book ON chunks(book_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chapter ON chunks(chapter_id);

CREATE TABLE IF NOT EXISTS tasks (
    id            TEXT PRIMARY KEY,
    book_id       TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL,
    type          TEXT NOT NULL DEFAULT 'ingest',
    status        TEXT NOT NULL DEFAULT 'pending',
    progress      INTEGER NOT NULL DEFAULT 0,
    error_msg     TEXT DEFAULT '',
    stages_log    TEXT DEFAULT '[]',
    dispatched_at TIMESTAMP,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tasks_book ON tasks(book_id);

CREATE TABLE IF NOT EXISTS token_usage (
    id                TEXT PRIMARY KEY,
    task_id           TEXT DEFAULT '',
    book_id           TEXT DEFAULT '',
    task_type         TEXT NOT NULL DEFAULT 'summary',
    llm_provider      TEXT NOT NULL DEFAULT '',
    llm_model         TEXT NOT NULL DEFAULT '',
    call_site         TEXT NOT NULL DEFAULT '',
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_token_usage_book     ON token_usage(book_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_created   ON token_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_provider  ON token_usage(created_at, llm_provider);

CREATE TABLE IF NOT EXISTS transfer_jobs (
    id               TEXT PRIMARY KEY,
    book_id          TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    type             TEXT NOT NULL,
    status           TEXT NOT NULL,
    stage            TEXT NOT NULL DEFAULT '',
    progress         INTEGER NOT NULL DEFAULT 0,
    error_msg        TEXT NOT NULL DEFAULT '',
    upload_path      TEXT NOT NULL DEFAULT '',
    target_file_name TEXT NOT NULL DEFAULT '',
    source_title     TEXT NOT NULL DEFAULT '',
    preview_json     TEXT NOT NULL DEFAULT '{}',
    created_at       TIMESTAMP NOT NULL,
    updated_at       TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transfer_jobs_book  ON transfer_jobs(book_id, created_at);
CREATE INDEX IF NOT EXISTS idx_transfer_jobs_status ON transfer_jobs(status, created_at);

CREATE TABLE IF NOT EXISTS api_tokens (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    token_hash    TEXT NOT NULL UNIQUE,
    token_suffix  TEXT DEFAULT '',
    alias         TEXT DEFAULT '',
    last_used_at  TIMESTAMP,
    expires_at    TIMESTAMP,
    is_revoked    INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id                   TEXT PRIMARY KEY,
    user_id              TEXT NOT NULL,
    title                TEXT DEFAULT '',
    book_ids             TEXT DEFAULT '[]',
    memory_summary       TEXT NOT NULL DEFAULT '',
    memory_updated_at    TIMESTAMP,
    memory_message_count INTEGER NOT NULL DEFAULT 0,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    citations  TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);
