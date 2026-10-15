package service

import (
	"archive/zip"
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"hash"
	"io"
	"math"
	"os"
	"path/filepath"
	"strings"
	"unicode"
	"unicode/utf8"

	"github.com/google/uuid"

	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/models"
)

const (
	transferArchiveVersion = 1
	maxTransferArchiveSize = int64(8 << 30)
	maxTransferEntrySize   = uint64(8 << 30)
)

type archiveBook struct {
	SourceBookID   string          `json:"source_book_id"`
	Title          string          `json:"title"`
	Summary        string          `json:"summary"`
	ReadingGuide   string          `json:"reading_guide"`
	ReferenceIndex string          `json:"reference_index"`
	Keywords       json.RawMessage `json:"keywords"`
	Fingerprint    string          `json:"fingerprint"`
}

type archiveChapter struct {
	ID          string          `json:"id"`
	Title       string          `json:"title"`
	Level       int             `json:"level"`
	SortOrder   int             `json:"sort_order"`
	ContentHash string          `json:"content_sha256"`
	Summary     string          `json:"summary"`
	Keywords    json.RawMessage `json:"keywords"`
	Definitions json.RawMessage `json:"definitions"`
}

type archiveVector struct {
	ID          string    `json:"id"`
	BookID      string    `json:"book_id"`
	ChapterID   string    `json:"chapter_id"`
	Content     string    `json:"content"`
	Position    int       `json:"position"`
	TokenCount  int       `json:"token_count"`
	StartOffset int       `json:"start_offset"`
	EndOffset   int       `json:"end_offset"`
	Embedding   []float32 `json:"embedding"`
}

type archiveManifest struct {
	Version      int               `json:"version"`
	SourceBookID string            `json:"source_book_id"`
	Title        string            `json:"title"`
	Fingerprint  string            `json:"fingerprint"`
	ChapterCount int               `json:"chapter_count"`
	VectorCount  int               `json:"vector_count"`
	EmbeddingDim int               `json:"embedding_dim"`
	Checksums    map[string]string `json:"checksums"`
}

type openedArchive struct {
	reader   *zip.ReadCloser
	files    map[string]*zip.File
	manifest archiveManifest
	book     archiveBook
	chapters []archiveChapter
}

func (a *openedArchive) Close() error {
	return a.reader.Close()
}

func (a *openedArchive) vectorRecords(consume func(archiveVector) error) error {
	file, ok := a.files["vectors.jsonl"]
	if !ok {
		return errors.New("archive is missing vectors.jsonl")
	}
	src, err := file.Open()
	if err != nil {
		return err
	}
	defer src.Close()
	scanner := bufio.NewScanner(src)
	scanner.Buffer(make([]byte, 64*1024), 16*1024*1024)
	for scanner.Scan() {
		var record archiveVector
		if err := json.Unmarshal(scanner.Bytes(), &record); err != nil {
			return fmt.Errorf("decode vector record: %w", err)
		}
		if err := consume(record); err != nil {
			return err
		}
	}
	if err := scanner.Err(); err != nil {
		return fmt.Errorf("read vectors.jsonl: %w", err)
	}
	return nil
}

func writeBookArchive(
	path string,
	book models.Book,
	chapters []models.Chapter,
	worker *coordinator.WorkerClient,
	onVector func(int),
) (int, error) {
	out, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return 0, fmt.Errorf("create export archive: %w", err)
	}
	closed := false
	defer func() {
		if !closed {
			_ = out.Close()
		}
	}()

	zipWriter := zip.NewWriter(out)
	hashes := make(map[string]string, 3)
	openHashedEntry := func(name string) (*json.Encoder, hash.Hash, error) {
		entry, err := zipWriter.Create(name)
		if err != nil {
			return nil, nil, err
		}
		digest := sha256.New()
		return json.NewEncoder(io.MultiWriter(entry, digest)), digest, nil
	}

	bookInfo := archiveBook{
		SourceBookID:   book.ID,
		Title:          book.Title,
		Summary:        book.Summary,
		ReadingGuide:   book.ReadingGuide,
		ReferenceIndex: book.ReferenceIndex,
		Keywords:       validJSONOr(book.Keywords, "[]"),
	}
	bookInfo.Fingerprint = bookFingerprint(bookInfo.Title, chapters)
	bookEncoder, bookHash, err := openHashedEntry("book.json")
	if err != nil {
		return 0, err
	}
	if err := bookEncoder.Encode(bookInfo); err != nil {
		return 0, fmt.Errorf("write book metadata: %w", err)
	}
	hashes["book.json"] = hex.EncodeToString(bookHash.Sum(nil))

	chapterEncoder, chapterHash, err := openHashedEntry("chapters.jsonl")
	if err != nil {
		return 0, err
	}
	for _, chapter := range chapters {
		record := archiveChapter{
			ID: chapter.ID, Title: chapter.Title, Level: chapter.Level, SortOrder: chapter.SortOrder,
			ContentHash: contentHash(chapter.Content), Summary: chapter.Summary,
			Keywords: validJSONOr(chapter.Keywords, "[]"), Definitions: validJSONOr(chapter.Definitions, "[]"),
		}
		if err := chapterEncoder.Encode(record); err != nil {
			return 0, fmt.Errorf("write chapter metadata: %w", err)
		}
	}
	hashes["chapters.jsonl"] = hex.EncodeToString(chapterHash.Sum(nil))

	vectorEncoder, vectorHash, err := openHashedEntry("vectors.jsonl")
	if err != nil {
		return 0, err
	}
	vectorCount := 0
	embeddingDim := 0
	err = worker.ExportBookVectors(book.ID, func(vector coordinator.VectorRecord) error {
		if vector.BookID != book.ID {
			return fmt.Errorf("worker returned vector for unexpected book %q", vector.BookID)
		}
		if len(vector.Embedding) == 0 {
			return fmt.Errorf("vector %q has no embedding", vector.ID)
		}
		if embeddingDim == 0 {
			embeddingDim = len(vector.Embedding)
		} else if len(vector.Embedding) != embeddingDim {
			return fmt.Errorf("vector %q has a different embedding dimension", vector.ID)
		}
		record := archiveVector{
			ID: vector.ID, BookID: vector.BookID, ChapterID: vector.ChapterID, Content: vector.Content,
			Position: vector.Position, TokenCount: vector.TokenCount,
			StartOffset: vector.StartOffset, EndOffset: vector.EndOffset, Embedding: vector.Embedding,
		}
		if err := vectorEncoder.Encode(record); err != nil {
			return fmt.Errorf("write vector record: %w", err)
		}
		vectorCount++
		if onVector != nil && vectorCount%128 == 0 {
			onVector(vectorCount)
		}
		return nil
	})
	if err != nil {
		return 0, fmt.Errorf("export vectors: %w", err)
	}
	hashes["vectors.jsonl"] = hex.EncodeToString(vectorHash.Sum(nil))

	manifest := archiveManifest{
		Version: transferArchiveVersion, SourceBookID: book.ID, Title: book.Title,
		Fingerprint: bookInfo.Fingerprint, ChapterCount: len(chapters), VectorCount: vectorCount,
		EmbeddingDim: embeddingDim, Checksums: hashes,
	}
	manifestEntry, err := zipWriter.Create("manifest.json")
	if err != nil {
		return 0, err
	}
	if err := json.NewEncoder(manifestEntry).Encode(manifest); err != nil {
		return 0, fmt.Errorf("write archive manifest: %w", err)
	}
	if err := zipWriter.Close(); err != nil {
		return 0, fmt.Errorf("close export archive: %w", err)
	}
	if err := out.Sync(); err != nil {
		return 0, fmt.Errorf("sync export archive: %w", err)
	}
	if err := out.Close(); err != nil {
		return 0, fmt.Errorf("close export file: %w", err)
	}
	closed = true
	return vectorCount, nil
}

func openBookArchive(path string) (*openedArchive, error) {
	reader, err := zip.OpenReader(path)
	if err != nil {
		return nil, fmt.Errorf("open ZIP archive: %w", err)
	}
	fail := func(err error) (*openedArchive, error) {
		_ = reader.Close()
		return nil, err
	}
	files := make(map[string]*zip.File, len(reader.File))
	var expanded int64
	for _, file := range reader.File {
		if file.Name == "" || filepath.IsAbs(file.Name) || strings.Contains(file.Name, `\`) ||
			strings.Contains(file.Name, "../") || strings.HasPrefix(file.Name, "./") {
			return fail(fmt.Errorf("unsafe archive entry %q", file.Name))
		}
		if file.CompressedSize64 > 0 && file.UncompressedSize64/file.CompressedSize64 > 1000 {
			return fail(fmt.Errorf("archive entry %q has an excessive compression ratio", file.Name))
		}
		if _, exists := files[file.Name]; exists {
			return fail(fmt.Errorf("duplicate archive entry %q", file.Name))
		}
		switch file.Name {
		case "manifest.json", "book.json", "chapters.jsonl", "vectors.jsonl":
		default:
			return fail(fmt.Errorf("unexpected archive entry %q", file.Name))
		}
		if file.UncompressedSize64 > maxTransferEntrySize {
			return fail(fmt.Errorf("archive entry %q exceeds size limit", file.Name))
		}
		expanded += int64(file.UncompressedSize64)
		if expanded > maxTransferArchiveSize {
			return fail(errors.New("archive exceeds total uncompressed size limit"))
		}
		files[file.Name] = file
	}
	if len(files) != 4 {
		return fail(errors.New("archive must contain manifest.json, book.json, chapters.jsonl, and vectors.jsonl"))
	}

	manifestBytes, err := readArchiveEntry(files["manifest.json"], 1<<20)
	if err != nil {
		return fail(fmt.Errorf("read manifest: %w", err))
	}
	var manifest archiveManifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return fail(fmt.Errorf("decode manifest: %w", err))
	}
	if manifest.Version != transferArchiveVersion {
		return fail(fmt.Errorf("unsupported archive version %d", manifest.Version))
	}
	if manifest.SourceBookID == "" || manifest.Title == "" || manifest.Fingerprint == "" {
		return fail(errors.New("archive manifest is missing required book metadata"))
	}
	for _, name := range []string{"book.json", "chapters.jsonl", "vectors.jsonl"} {
		want, ok := manifest.Checksums[name]
		if !ok {
			return fail(fmt.Errorf("manifest has no checksum for %s", name))
		}
		got, err := hashArchiveEntry(files[name])
		if err != nil {
			return fail(fmt.Errorf("verify %s: %w", name, err))
		}
		if !strings.EqualFold(want, got) {
			return fail(fmt.Errorf("checksum mismatch for %s", name))
		}
	}

	bookBytes, err := readArchiveEntry(files["book.json"], 16<<20)
	if err != nil {
		return fail(fmt.Errorf("read book metadata: %w", err))
	}
	var book archiveBook
	if err := json.Unmarshal(bookBytes, &book); err != nil {
		return fail(fmt.Errorf("decode book metadata: %w", err))
	}
	if book.Title == "" || book.SourceBookID == "" {
		return fail(errors.New("book metadata is incomplete"))
	}

	opened := &openedArchive{reader: reader, files: files, manifest: manifest, book: book}
	if err := opened.readChapters(); err != nil {
		return fail(err)
	}
	return opened, nil
}

func (a *openedArchive) readChapters() error {
	file, ok := a.files["chapters.jsonl"]
	if !ok {
		return errors.New("archive is missing chapters.jsonl")
	}
	src, err := file.Open()
	if err != nil {
		return err
	}
	defer src.Close()
	scanner := bufio.NewScanner(src)
	scanner.Buffer(make([]byte, 64*1024), 16*1024*1024)
	seen := make(map[string]struct{})
	for scanner.Scan() {
		var chapter archiveChapter
		if err := json.Unmarshal(scanner.Bytes(), &chapter); err != nil {
			return fmt.Errorf("decode chapter metadata: %w", err)
		}
		if chapter.ID == "" || chapter.ContentHash == "" {
			return errors.New("chapter metadata is missing an id or content hash")
		}
		if _, duplicate := seen[chapter.ID]; duplicate {
			return fmt.Errorf("duplicate chapter id %q", chapter.ID)
		}
		seen[chapter.ID] = struct{}{}
		a.chapters = append(a.chapters, chapter)
	}
	if err := scanner.Err(); err != nil {
		return fmt.Errorf("read chapter metadata: %w", err)
	}
	if len(a.chapters) != a.manifest.ChapterCount {
		return fmt.Errorf("chapter count mismatch: manifest says %d, archive has %d", a.manifest.ChapterCount, len(a.chapters))
	}
	if bookFingerprint(a.book.Title, archiveChaptersForFingerprint(a.chapters)) != a.manifest.Fingerprint ||
		a.book.Fingerprint != a.manifest.Fingerprint {
		return errors.New("book fingerprint mismatch")
	}
	return nil
}

func archiveChaptersForFingerprint(chapters []archiveChapter) []models.Chapter {
	result := make([]models.Chapter, 0, len(chapters))
	for _, chapter := range chapters {
		result = append(result, models.Chapter{
			Title:     chapter.Title,
			Content:   chapter.ContentHash,
			SortOrder: chapter.SortOrder,
		})
	}
	return result
}

func readArchiveEntry(file *zip.File, limit int64) ([]byte, error) {
	if file.UncompressedSize64 > uint64(limit) {
		return nil, fmt.Errorf("entry %q exceeds read limit", file.Name)
	}
	reader, err := file.Open()
	if err != nil {
		return nil, err
	}
	defer reader.Close()
	return io.ReadAll(io.LimitReader(reader, limit+1))
}

func hashArchiveEntry(file *zip.File) (string, error) {
	reader, err := file.Open()
	if err != nil {
		return "", err
	}
	defer reader.Close()
	digest := sha256.New()
	if _, err := io.Copy(digest, io.LimitReader(reader, maxTransferArchiveSize+1)); err != nil {
		return "", err
	}
	return hex.EncodeToString(digest.Sum(nil)), nil
}

func sanitizeExportFilename(title, taskID string) string {
	var cleaned strings.Builder
	for _, r := range title {
		if unicode.IsControl(r) || strings.ContainsRune(`/\:*?"<>|`, r) {
			continue
		}
		cleaned.WriteRune(r)
	}
	name := strings.Trim(strings.TrimSpace(cleaned.String()), ".")
	if name == "" {
		name = "book"
	}
	suffix := "-" + strings.ReplaceAll(taskID, "-", "")[:8] + ".zip"
	maxTitleLength := 100 - utf8.RuneCountInString(suffix)
	maxTitleBytes := 255 - len(suffix)
	var truncated strings.Builder
	titleLength := 0
	for _, r := range name {
		if titleLength >= maxTitleLength || truncated.Len()+utf8.RuneLen(r) > maxTitleBytes {
			break
		}
		truncated.WriteRune(r)
		titleLength++
	}
	name = strings.Trim(strings.TrimSpace(truncated.String()), ".")
	if name == "" {
		name = "book"
	}
	return name + suffix
}

func validJSONOr(value, fallback string) json.RawMessage {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" || !json.Valid([]byte(trimmed)) {
		return json.RawMessage(fallback)
	}
	return json.RawMessage(trimmed)
}

func contentHash(content string) string {
	sum := sha256.Sum256([]byte(content))
	return hex.EncodeToString(sum[:])
}

func bookFingerprint(title string, chapters []models.Chapter) string {
	ordered := append([]models.Chapter(nil), chapters...)
	// Input order is already sort_order ordered. Include the order/title/hash
	// so identical text split into a different chapter structure is not a
	// false match.
	var data strings.Builder
	data.WriteString(strings.TrimSpace(title))
	data.WriteByte('\n')
	for _, chapter := range ordered {
		hash := chapter.Content
		if len(hash) != sha256.Size*2 {
			hash = contentHash(chapter.Content)
		}
		fmt.Fprintf(&data, "%d\x00%s\x00%s\n", chapter.SortOrder, strings.TrimSpace(chapter.Title), hash)
	}
	return contentHash(data.String())
}

func validateVectorRecord(record archiveVector, dimension int, chapters map[string]struct{}) error {
	if record.ID == "" || record.BookID == "" || len(record.Embedding) == 0 {
		return errors.New("vector record is missing an id, book id, or embedding")
	}
	if dimension > 0 && len(record.Embedding) != dimension {
		return fmt.Errorf("vector %q has dimension %d, expected %d", record.ID, len(record.Embedding), dimension)
	}
	if record.ChapterID != "" {
		if _, ok := chapters[record.ChapterID]; !ok {
			return fmt.Errorf("vector %q refers to unknown chapter %q", record.ID, record.ChapterID)
		}
	}
	for _, value := range record.Embedding {
		if math.IsNaN(float64(value)) || math.IsInf(float64(value), 0) {
			return fmt.Errorf("vector %q contains a non-finite embedding value", record.ID)
		}
	}
	return nil
}

func stableImportedID(jobID, sourceID string) string {
	return uuid.NewSHA1(uuid.NameSpaceOID, []byte(jobID+"\x00"+sourceID)).String()
}
