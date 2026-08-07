-- Local path to the book's cover image (data/covers/<book_id><ext>), set by
-- whichever of these completes first: an explicit cover_url given at import
-- time (BookHandler.Import), auto-extraction from the source EPUB during
-- ingestion, or — if neither produced anything — a title-based image
-- generated as a fallback (see worker/src/util/cover_generator.py and
-- grpcserver.ReportComplete/BookHandler.Import). Empty until one of those
-- succeeds.
ALTER TABLE books ADD COLUMN cover_path TEXT NOT NULL DEFAULT '';
