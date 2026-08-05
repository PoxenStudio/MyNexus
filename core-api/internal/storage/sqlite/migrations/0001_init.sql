-- Initial schema, mirrors docs/系统设计文档.md §5.2.

CREATE TABLE IF NOT EXISTS books (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    title         TEXT NOT NULL DEFAULT '',
    author        TEXT DEFAULT '',
    publisher     TEXT DEFAULT '',
    language      TEXT DEFAULT '',
    publish_date  TEXT DEFAULT '',
    isbn          TEXT DEFAULT '',
    source_origin TEXT NOT NULL DEFAULT 'DirectUpload',
    source_format TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    tags          TEXT DEFAULT '[]',
    category      TEXT DEFAULT '',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chapters (
    id         TEXT PRIMARY KEY,
    book_id    TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    title      TEXT NOT NULL DEFAULT '',
    level      INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    content    TEXT DEFAULT '',
    summary    TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_chapters_book ON chapters(book_id);

CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    chapter_id  TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    book_id     TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    position    INTEGER NOT NULL DEFAULT 0,
    vector_id   TEXT DEFAULT '',
    keywords    TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_chunks_book ON chunks(book_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chapter ON chunks(chapter_id);

CREATE TABLE IF NOT EXISTS tasks (
    id         TEXT PRIMARY KEY,
    book_id    TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    user_id    TEXT NOT NULL,
    type       TEXT NOT NULL DEFAULT 'ingest',
    status     TEXT NOT NULL DEFAULT 'pending',
    progress   INTEGER NOT NULL DEFAULT 0,
    error_msg  TEXT DEFAULT '',
    stages_log TEXT DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tasks_book ON tasks(book_id);

CREATE TABLE IF NOT EXISTS api_tokens (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    token_hash    TEXT NOT NULL UNIQUE,
    token_suffix  TEXT DEFAULT '',     -- last 4 chars of the raw token, for display only
    alias         TEXT DEFAULT '',
    last_used_at  DATETIME,
    expires_at    DATETIME,
    is_revoked    INTEGER NOT NULL DEFAULT 0,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT DEFAULT '',
    book_ids   TEXT DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    citations  TEXT DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);
