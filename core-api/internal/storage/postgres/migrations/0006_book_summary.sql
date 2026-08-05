-- Mirrors storage/sqlite/migrations/0005_book_summary.sql.

ALTER TABLE books ADD COLUMN summary TEXT NOT NULL DEFAULT '';
