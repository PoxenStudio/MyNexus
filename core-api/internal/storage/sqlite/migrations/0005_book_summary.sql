-- Whole-book summary, produced by the map-reduce summarization pipeline:
-- each chapter's summary (chapters.summary, added in 0001_init.sql but never
-- populated until now) is generated first (map), then reduced into this
-- book-level summary. See worker/src/pipelines/summary.py.

ALTER TABLE books ADD COLUMN summary TEXT NOT NULL DEFAULT '';
