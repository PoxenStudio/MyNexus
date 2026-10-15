CREATE UNIQUE INDEX IF NOT EXISTS idx_books_mybooks_id_unique
    ON books(mybooks_id)
    WHERE mybooks_id IS NOT NULL;
