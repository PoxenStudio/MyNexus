-- Per-chapter content keywords and LLM-extracted definitions, produced by
-- worker/src/pipelines/summary.py's SummaryPipeline.run() alongside each
-- chapter's summary. keywords is this chapter's own top-N terms, distinct
-- from books.keywords (the whole-book aggregate). definitions is a JSON
-- array of {"name","content"} objects — the book's own explanation of a
-- term, not one the model invented. Both empty until a summarize task has
-- (re)generated this chapter's summary at least once since this migration.
-- NOTE: RunMigrations splits a script on the literal statement-terminator
-- character (see storage/migrator.go's splitStatements), so a comment in
-- *any* migration file must not contain that character either — it would
-- get sliced into its own bogus statement and fail with a syntax error,
-- exactly like this file did the first time around.

ALTER TABLE chapters ADD COLUMN keywords TEXT NOT NULL DEFAULT '[]';
ALTER TABLE chapters ADD COLUMN definitions TEXT NOT NULL DEFAULT '[]';
