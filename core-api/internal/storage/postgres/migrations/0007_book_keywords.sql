-- Mirrors storage/sqlite/migrations/0006_book_keywords.sql.

ALTER TABLE books ADD COLUMN keywords TEXT NOT NULL DEFAULT '[]';
