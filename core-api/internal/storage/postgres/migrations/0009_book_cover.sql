-- Mirrors storage/sqlite/migrations/0008_book_cover.sql — see that file for
-- the full rationale.

ALTER TABLE books ADD COLUMN cover_path TEXT NOT NULL DEFAULT '';
