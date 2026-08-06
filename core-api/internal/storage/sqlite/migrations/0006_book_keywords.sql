-- Whole-book content keywords, reduced from each chapter's summary during
-- summarization (see worker/src/pipelines/summary.py) — distinct from
-- books.tags (user-/MyBooks-assigned labels). JSON array of
-- {"term","weight"} objects, sorted by weight descending, empty until a
-- summarize task completes for this book.

ALTER TABLE books ADD COLUMN keywords TEXT NOT NULL DEFAULT '[]';
