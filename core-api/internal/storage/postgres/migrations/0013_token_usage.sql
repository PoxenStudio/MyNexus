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
