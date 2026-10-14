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
CREATE INDEX IF NOT EXISTS idx_transfer_jobs_book ON transfer_jobs(book_id, created_at);
CREATE INDEX IF NOT EXISTS idx_transfer_jobs_status ON transfer_jobs(status, created_at);
