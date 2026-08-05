package service

import (
	"database/sql"
	"fmt"
	"io"
	"mime/multipart"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/google/uuid"

	"mynexus/core-api/internal/models"
)

type BookService struct {
	db        *sql.DB
	uploadDir string
}

func NewBookService(db *sql.DB, uploadDir string) *BookService {
	return &BookService{db: db, uploadDir: uploadDir}
}

// CreateBook inserts a new book row in pending status. FilePath is filled in
// afterwards once the upload is saved to disk.
func (s *BookService) CreateBook(userID, sourceFormat, sourceOrigin string) (*models.Book, error) {
	now := time.Now().UTC().Format(time.RFC3339)
	book := &models.Book{
		ID:           uuid.NewString(),
		UserID:       userID,
		SourceOrigin: sourceOrigin,
		SourceFormat: sourceFormat,
		Status:       models.BookStatusPending,
		Tags:         "[]",
		CreatedAt:    now,
		UpdatedAt:    now,
	}

	_, err := s.db.Exec(
		`INSERT INTO books (id, user_id, title, author, publisher, language, publish_date, isbn,
			source_origin, source_format, file_path, status, tags, category, created_at, updated_at)
		 VALUES (?, ?, '', '', '', '', '', '', ?, ?, '', ?, ?, '', ?, ?)`,
		book.ID, book.UserID, book.SourceOrigin, book.SourceFormat, book.Status, book.Tags,
		book.CreatedAt, book.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("insert book: %w", err)
	}
	return book, nil
}

// SaveUploadedFile persists the multipart file under uploadDir/<bookID><ext> and
// records the resulting path on the book row. The original filename is kept
// out of the on-disk path (it's passed to Worker separately as a title hint
// for formats with no embedded metadata, e.g. TXT) so storage stays free of
// user-controlled names.
func (s *BookService) SaveUploadedFile(bookID string, header *multipart.FileHeader) (string, error) {
	if err := os.MkdirAll(s.uploadDir, 0o755); err != nil {
		return "", fmt.Errorf("create upload dir: %w", err)
	}

	ext := strings.ToLower(filepath.Ext(header.Filename))
	destPath := filepath.Join(s.uploadDir, bookID+ext)

	src, err := header.Open()
	if err != nil {
		return "", fmt.Errorf("open uploaded file: %w", err)
	}
	defer src.Close()

	dst, err := os.Create(destPath)
	if err != nil {
		return "", fmt.Errorf("create dest file: %w", err)
	}
	defer dst.Close()

	if _, err := io.Copy(dst, src); err != nil {
		return "", fmt.Errorf("write dest file: %w", err)
	}

	if _, err := s.db.Exec(`UPDATE books SET file_path = ?, updated_at = ? WHERE id = ?`,
		destPath, time.Now().UTC().Format(time.RFC3339), bookID); err != nil {
		return "", fmt.Errorf("update book file_path: %w", err)
	}
	return destPath, nil
}

func (s *BookService) SetStatus(bookID, status string) error {
	_, err := s.db.Exec(`UPDATE books SET status = ?, updated_at = ? WHERE id = ?`,
		status, time.Now().UTC().Format(time.RFC3339), bookID)
	return err
}

// ApplyParsedMetadata fills in title/author/language extracted by the Worker,
// but never overwrites fields the user already edited manually.
func (s *BookService) ApplyParsedMetadata(bookID, title, author, language string) error {
	_, err := s.db.Exec(
		`UPDATE books SET
			title = CASE WHEN title = '' THEN ? ELSE title END,
			author = CASE WHEN author = '' THEN ? ELSE author END,
			language = CASE WHEN language = '' THEN ? ELSE language END,
			updated_at = ?
		 WHERE id = ?`,
		title, author, language, time.Now().UTC().Format(time.RFC3339), bookID,
	)
	return err
}

func (s *BookService) GetBook(id string) (*models.Book, error) {
	row := s.db.QueryRow(
		`SELECT id, user_id, title, author, publisher, language, publish_date, isbn,
			source_origin, source_format, file_path, status, tags, category, summary, created_at, updated_at
		 FROM books WHERE id = ?`, id)
	return scanBook(row)
}

func (s *BookService) ListBooks(page, size int, status, q string) ([]models.Book, int64, error) {
	if page < 1 {
		page = 1
	}
	if size < 1 || size > 200 {
		size = 20
	}

	where := "WHERE 1=1"
	args := []any{}
	if status != "" {
		where += " AND status = ?"
		args = append(args, status)
	}
	if q != "" {
		where += " AND (title LIKE ? OR author LIKE ?)"
		like := "%" + q + "%"
		args = append(args, like, like)
	}

	var total int64
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM books `+where, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count books: %w", err)
	}

	listArgs := append(append([]any{}, args...), size, (page-1)*size)
	rows, err := s.db.Query(
		`SELECT id, user_id, title, author, publisher, language, publish_date, isbn,
			source_origin, source_format, file_path, status, tags, category, summary, created_at, updated_at
		 FROM books `+where+` ORDER BY created_at DESC LIMIT ? OFFSET ?`, listArgs...)
	if err != nil {
		return nil, 0, fmt.Errorf("list books: %w", err)
	}
	defer rows.Close()

	var books []models.Book
	for rows.Next() {
		b, err := scanBookRows(rows)
		if err != nil {
			return nil, 0, err
		}
		books = append(books, *b)
	}
	return books, total, rows.Err()
}

func (s *BookService) UpdateBook(id, title, author, category string, tags string) error {
	_, err := s.db.Exec(
		`UPDATE books SET title = ?, author = ?, category = ?, tags = ?, updated_at = ? WHERE id = ?`,
		title, author, category, tags, time.Now().UTC().Format(time.RFC3339), id,
	)
	return err
}

func (s *BookService) DeleteBook(id string) error {
	book, err := s.GetBook(id)
	if err != nil {
		return err
	}
	if _, err := s.db.Exec(`DELETE FROM books WHERE id = ?`, id); err != nil {
		return fmt.Errorf("delete book: %w", err)
	}
	if book.FilePath != "" {
		_ = os.Remove(book.FilePath)
	}
	return nil
}

// SaveChapters replaces bookID's chapters. Chapter IDs are assigned by
// Worker (not generated here) so it can tag chunks with the right chapter_id
// in the same pipeline run — see .claude/memory/mynexus_m2_decisions.md.
func (s *BookService) SaveChapters(bookID string, chapters []ParsedChapter) error {
	tx, err := s.db.Begin()
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DELETE FROM chapters WHERE book_id = ?`, bookID); err != nil {
		return fmt.Errorf("clear chapters: %w", err)
	}

	stmt, err := tx.Prepare(
		`INSERT INTO chapters (id, book_id, title, level, sort_order, content, summary)
		 VALUES (?, ?, ?, ?, ?, ?, '')`)
	if err != nil {
		return fmt.Errorf("prepare insert chapter: %w", err)
	}
	defer stmt.Close()

	for _, c := range chapters {
		id := c.ID
		if id == "" {
			id = uuid.NewString()
		}
		if _, err := stmt.Exec(id, bookID, c.Title, c.Level, c.SortOrder, c.Content); err != nil {
			return fmt.Errorf("insert chapter: %w", err)
		}
	}

	return tx.Commit()
}

// SaveChunks replaces bookID's chunks. Like chapters, chunk IDs come from
// Worker (they double as the vector store's key).
func (s *BookService) SaveChunks(bookID string, chunks []ParsedChunk) error {
	tx, err := s.db.Begin()
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DELETE FROM chunks WHERE book_id = ?`, bookID); err != nil {
		return fmt.Errorf("clear chunks: %w", err)
	}

	stmt, err := tx.Prepare(
		`INSERT INTO chunks (id, chapter_id, book_id, content, token_count, position, vector_id, keywords)
		 VALUES (?, ?, ?, ?, ?, ?, ?, '[]')`)
	if err != nil {
		return fmt.Errorf("prepare insert chunk: %w", err)
	}
	defer stmt.Close()

	for _, c := range chunks {
		if _, err := stmt.Exec(c.ID, c.ChapterID, bookID, c.Content, c.TokenCount, c.Position, c.VectorID); err != nil {
			return fmt.Errorf("insert chunk: %w", err)
		}
	}

	return tx.Commit()
}

func (s *BookService) ListChunks(bookID, chapterID string, page, size int) ([]models.Chunk, int64, error) {
	if page < 1 {
		page = 1
	}
	if size < 1 || size > 500 {
		size = 50
	}

	where := "WHERE book_id = ?"
	args := []any{bookID}
	if chapterID != "" {
		where += " AND chapter_id = ?"
		args = append(args, chapterID)
	}

	var total int64
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM chunks `+where, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count chunks: %w", err)
	}

	listArgs := append(append([]any{}, args...), size, (page-1)*size)
	rows, err := s.db.Query(
		`SELECT id, chapter_id, book_id, content, token_count, position, vector_id, keywords
		 FROM chunks `+where+` ORDER BY position ASC LIMIT ? OFFSET ?`, listArgs...)
	if err != nil {
		return nil, 0, fmt.Errorf("list chunks: %w", err)
	}
	defer rows.Close()

	var chunks []models.Chunk
	for rows.Next() {
		var c models.Chunk
		if err := rows.Scan(&c.ID, &c.ChapterID, &c.BookID, &c.Content, &c.TokenCount, &c.Position, &c.VectorID, &c.Keywords); err != nil {
			return nil, 0, fmt.Errorf("scan chunk: %w", err)
		}
		chunks = append(chunks, c)
	}
	return chunks, total, rows.Err()
}

func (s *BookService) ListChapters(bookID string) ([]models.Chapter, error) {
	rows, err := s.db.Query(
		`SELECT id, book_id, title, level, sort_order, content, summary
		 FROM chapters WHERE book_id = ? ORDER BY sort_order ASC`, bookID)
	if err != nil {
		return nil, fmt.Errorf("list chapters: %w", err)
	}
	defer rows.Close()

	var chapters []models.Chapter
	for rows.Next() {
		var c models.Chapter
		if err := rows.Scan(&c.ID, &c.BookID, &c.Title, &c.Level, &c.SortOrder, &c.Content, &c.Summary); err != nil {
			return nil, fmt.Errorf("scan chapter: %w", err)
		}
		chapters = append(chapters, c)
	}
	return chapters, rows.Err()
}

// UpdateChapterSummary persists one chapter's summary — the map step of
// worker/src/pipelines/summary.py's summarization run, called once per
// chapter as soon as it's ready (not batched), so progress survives a
// mid-run crash/failure.
func (s *BookService) UpdateChapterSummary(chapterID, summary string) error {
	_, err := s.db.Exec(`UPDATE chapters SET summary = ? WHERE id = ?`, summary, chapterID)
	return err
}

// SetBookSummary persists the whole-book summary — the reduce step, run once
// after every chapter has a summary.
func (s *BookService) SetBookSummary(bookID, summary string) error {
	_, err := s.db.Exec(`UPDATE books SET summary = ?, updated_at = ? WHERE id = ?`,
		summary, time.Now().UTC().Format(time.RFC3339), bookID)
	return err
}

// ChapterTitle looks up a single chapter's title, used to enrich search
// results with a human-readable chapter reference.
func (s *BookService) ChapterTitle(chapterID string) (string, error) {
	var title string
	err := s.db.QueryRow(`SELECT title FROM chapters WHERE id = ?`, chapterID).Scan(&title)
	if err != nil {
		return "", err
	}
	return title, nil
}

// KeywordSearchResult is one hit from KeywordSearch, ranked by Postgres's
// ts_rank over the chunks.content_tsv generated column.
type KeywordSearchResult struct {
	ChunkID string
	BookID  string
	Score   float64
}

// KeywordSearch runs a GIN-indexed full-text query against chunks.content_tsv
// (see storage/postgres/migrations/0004_chunk_keyword_search.sql) — this only
// works against the Postgres backend; content_tsv/GIN don't exist on SQLite
// (positioned as small-scale/trial-only, see docs/系统设计文档.md), so callers
// must check cfg.Storage.Database == "postgres" before calling this.
func (s *BookService) KeywordSearch(query string, bookIDs []string, topK int) ([]KeywordSearchResult, error) {
	args := []any{query, query}
	where := `content_tsv @@ plainto_tsquery('simple', ?)`

	if len(bookIDs) > 0 {
		placeholders := make([]string, len(bookIDs))
		for i, id := range bookIDs {
			placeholders[i] = "?"
			args = append(args, id)
		}
		where += fmt.Sprintf(" AND book_id IN (%s)", strings.Join(placeholders, ", "))
	}
	args = append(args, topK)

	rows, err := s.db.Query(
		`SELECT id, book_id, ts_rank(content_tsv, plainto_tsquery('simple', ?)) AS rank
		 FROM chunks WHERE `+where+`
		 ORDER BY rank DESC LIMIT ?`,
		args...,
	)
	if err != nil {
		return nil, fmt.Errorf("keyword search: %w", err)
	}
	defer rows.Close()

	var results []KeywordSearchResult
	for rows.Next() {
		var r KeywordSearchResult
		if err := rows.Scan(&r.ChunkID, &r.BookID, &r.Score); err != nil {
			return nil, fmt.Errorf("scan keyword search result: %w", err)
		}
		results = append(results, r)
	}
	return results, rows.Err()
}

// ParsedChapter is the shape Worker sends back on task completion.
type ParsedChapter struct {
	ID        string
	Title     string
	Level     int
	SortOrder int
	Content   string
}

// ParsedChunk is the shape Worker sends back on task completion.
type ParsedChunk struct {
	ID         string
	ChapterID  string
	Content    string
	Position   int
	TokenCount int
	VectorID   string
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanBook(row rowScanner) (*models.Book, error) {
	return scanBookRows(row)
}

func scanBookRows(row rowScanner) (*models.Book, error) {
	var b models.Book
	err := row.Scan(&b.ID, &b.UserID, &b.Title, &b.Author, &b.Publisher, &b.Language, &b.PublishDate,
		&b.ISBN, &b.SourceOrigin, &b.SourceFormat, &b.FilePath, &b.Status, &b.Tags, &b.Category, &b.Summary,
		&b.CreatedAt, &b.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, err
	}
	if err != nil {
		return nil, fmt.Errorf("scan book: %w", err)
	}
	return &b, nil
}
