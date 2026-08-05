-- Postgres-only: GIN-indexed full-text search over chunk content, replacing
-- Worker's in-process BM25-over-full-corpus approach for large libraries (see
-- docs/系统设计文档.md's "已知局限" note and .claude/memory/mynexus_keyword_search_gin.md).
-- No SQLite equivalent — SQLite is positioned as a small-scale/trial-only
-- backend, so it keeps the existing brute-force BM25 path in Worker instead.
--
-- content_tsv is a generated column: Postgres maintains it automatically on
-- every INSERT/UPDATE to chunks.content, so Core API's existing SaveChunks
-- write path (unchanged, still reached only via Worker's HTTP callback) needs
-- no code changes at all to keep this index up to date.

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED;

CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv ON chunks USING GIN (content_tsv);
