-- Mirrors storage/sqlite/migrations/0010_chapter_keywords_definitions.sql.

ALTER TABLE chapters ADD COLUMN keywords TEXT NOT NULL DEFAULT '[]';
ALTER TABLE chapters ADD COLUMN definitions TEXT NOT NULL DEFAULT '[]';
