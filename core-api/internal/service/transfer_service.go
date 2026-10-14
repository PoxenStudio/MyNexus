package service

import (
	"archive/zip"
	"bufio"
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"hash"
	"io"
	"log"
	"mime/multipart"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"

	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/models"
)

const (
	TransferTypeExport = "export"
	TransferTypeImport = "import"

	TransferStatusPending              = "pending"
	TransferStatusProcessing           = "processing"
	TransferStatusAwaitingConfirmation = "awaiting_confirmation"
	TransferStatusCompleted            = "completed"
	TransferStatusFailed               = "failed"
	TransferStatusCanceled             = "canceled"

	MaxTransferUploadSize = int64(8 << 30)
	transferBatchSize     = 128
)

var ErrBookNotFound = errors.New("book not found")
var ErrTransferInProgress = errors.New("a book data import or export is already in progress")

type TransferJob struct {
	ID             string `json:"id"`
	BookID         string `json:"book_id"`
	Type           string `json:"type"`
	Status         string `json:"status"`
	Stage          string `json:"stage"`
	Progress       int    `json:"progress"`
	ErrorMsg       string `json:"error_msg"`
	TargetFileName string `json:"target_file_name,omitempty"`
	SourceTitle    string `json:"source_title,omitempty"`
	Preview        string `json:"preview,omitempty"`
	CreatedAt      string `json:"created_at"`
	UpdatedAt      string `json:"updated_at"`
	uploadPath     string
}

type TransferPreview struct {
	SourceTitle     string `json:"source_title"`
	TargetTitle     string `json:"target_title"`
	SourceChapters  int    `json:"source_chapters"`
	MatchedChapters int    `json:"matched_chapters"`
	SourceVectors   int    `json:"source_vectors"`
	MatchedVectors  int    `json:"matched_vectors"`
	ExactBookMatch  bool   `json:"exact_book_match"`
	Warning         string `json:"warning,omitempty"`
}

type TransferService struct {
	db               *sql.DB
	books            *BookService
	worker           *coordinator.WorkerClient
	exportDir        string
	importDir        string
	queue            chan string
	startOnce        sync.Once
	activeTransferMu sync.Mutex
	activeTransferID string
}

func NewTransferService(db *sql.DB, books *BookService, worker *coordinator.WorkerClient, dataDir string) *TransferService {
	return &TransferService{
		db: db, books: books, worker: worker,
		exportDir: filepath.Join(dataDir, "export"),
		importDir: filepath.Join(dataDir, "imports"),
		queue:     make(chan string, 128),
	}
}

func (s *TransferService) Start() error {
	if err := os.MkdirAll(s.exportDir, 0o750); err != nil {
		return fmt.Errorf("create export directory: %w", err)
	}
	if err := os.MkdirAll(s.importDir, 0o700); err != nil {
		return fmt.Errorf("create import directory: %w", err)
	}
	if _, err := s.db.Exec(
		`UPDATE transfer_jobs SET status = ?, stage = 'queued', progress = 0, updated_at = ?
		 WHERE status = ?`,
		TransferStatusPending, time.Now().UTC().Format(time.RFC3339Nano), TransferStatusProcessing,
	); err != nil {
		return fmt.Errorf("recover interrupted transfer jobs: %w", err)
	}
	type activeJob struct {
		id     string
		status string
	}
	var jobs []activeJob
	rows, err := s.db.Query(
		`SELECT id, status FROM transfer_jobs WHERE status IN (?, ?, ?) ORDER BY created_at ASC, id ASC`,
		TransferStatusPending, TransferStatusProcessing, TransferStatusAwaitingConfirmation,
	)
	if err != nil {
		return fmt.Errorf("load queued transfer jobs: %w", err)
	}
	for rows.Next() {
		var job activeJob
		if err := rows.Scan(&job.id, &job.status); err != nil {
			rows.Close()
			return fmt.Errorf("scan queued transfer job: %w", err)
		}
		jobs = append(jobs, job)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return fmt.Errorf("iterate queued transfer jobs: %w", err)
	}
	if err := rows.Close(); err != nil {
		return fmt.Errorf("close queued transfer jobs: %w", err)
	}
	s.startOnce.Do(func() { go s.runQueue() })
	if len(jobs) == 0 {
		return nil
	}
	s.activeTransferID = jobs[0].id
	for _, job := range jobs[1:] {
		if err := s.updateJob(job.id, func(j *TransferJob) {
			j.Status = TransferStatusFailed
			j.Stage = "failed"
			j.ErrorMsg = "Stopped during restart because only one book data transfer may be active at a time"
		}); err != nil {
			return fmt.Errorf("stop overlapping transfer job %s: %w", job.id, err)
		}
	}
	if jobs[0].status != TransferStatusAwaitingConfirmation {
		s.enqueue(jobs[0].id)
	}
	return nil
}

func (s *TransferService) enqueue(id string) {
	select {
	case s.queue <- id:
	default:
		go func() { s.queue <- id }()
	}
}

func (s *TransferService) runQueue() {
	for id := range s.queue {
		if err := s.runJob(id); err != nil {
			log.Printf("transfer task %s failed: %v", id, err)
		}
	}
}

func (s *TransferService) CreateExport(bookID string) (*TransferJob, error) {
	book, err := s.books.GetBook(bookID)
	if err != nil {
		return nil, ErrBookNotFound
	}
	var chapterData, chunkCount int
	if err := s.db.QueryRow(
		`SELECT COUNT(*) FROM chapters
		 WHERE book_id = ? AND (summary <> '' OR keywords <> '[]' OR definitions <> '[]')`, bookID,
	).Scan(&chapterData); err != nil {
		return nil, fmt.Errorf("check chapter data: %w", err)
	}
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM chunks WHERE book_id = ?`, bookID).Scan(&chunkCount); err != nil {
		return nil, fmt.Errorf("check book chunks: %w", err)
	}
	var keywords []json.RawMessage
	if err := json.Unmarshal([]byte(book.Keywords), &keywords); err != nil {
		return nil, fmt.Errorf("decode book keywords: %w", err)
	}
	if book.Summary == "" && len(keywords) == 0 && chapterData == 0 && chunkCount == 0 {
		return nil, errors.New("book has no exportable derived data")
	}
	reservation, err := s.claimTransfer()
	if err != nil {
		return nil, err
	}
	activeID := reservation
	queued := false
	defer func() {
		if !queued {
			s.releaseTransfer(activeID)
		}
	}()
	job, err := s.createJob(bookID, TransferTypeExport, "")
	if err != nil {
		return nil, err
	}
	activeID = job.ID
	s.bindTransfer(reservation, job.ID)
	job.TargetFileName = sanitizeExportFilename(book.Title, job.ID)
	if err := s.updateJob(job.ID, func(j *TransferJob) {
		j.TargetFileName = job.TargetFileName
		j.Stage = "queued"
	}); err != nil {
		_ = s.deleteJob(job.ID)
		return nil, err
	}
	job.Stage = "queued"
	s.enqueue(job.ID)
	queued = true
	return job, nil
}

func (s *TransferService) CreateImport(bookID string, fileHeader *multipart.FileHeader) (*TransferJob, error) {
	if _, err := s.books.GetBook(bookID); err != nil {
		return nil, ErrBookNotFound
	}
	if fileHeader.Size <= 0 || fileHeader.Size > MaxTransferUploadSize {
		return nil, fmt.Errorf("archive file must be between 1 byte and %d bytes", MaxTransferUploadSize)
	}
	if err := os.MkdirAll(s.importDir, 0o700); err != nil {
		return nil, fmt.Errorf("create import directory: %w", err)
	}
	reservation, err := s.claimTransfer()
	if err != nil {
		return nil, err
	}
	activeID := reservation
	queued := false
	defer func() {
		if !queued {
			s.releaseTransfer(activeID)
		}
	}()
	job, err := s.createJob(bookID, TransferTypeImport, "")
	if err != nil {
		return nil, err
	}
	activeID = job.ID
	s.bindTransfer(reservation, job.ID)
	tempPath := filepath.Join(s.importDir, "."+job.ID+".part")
	archivePath := filepath.Join(s.importDir, job.ID+".zip")
	src, err := fileHeader.Open()
	if err != nil {
		_ = s.deleteJob(job.ID)
		return nil, fmt.Errorf("open uploaded archive: %w", err)
	}
	dst, err := os.OpenFile(tempPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		src.Close()
		_ = s.deleteJob(job.ID)
		return nil, fmt.Errorf("create import staging file: %w", err)
	}
	n, copyErr := io.Copy(dst, io.LimitReader(src, MaxTransferUploadSize+1))
	srcCloseErr := src.Close()
	syncErr := dst.Sync()
	closeErr := dst.Close()
	if copyErr != nil || srcCloseErr != nil || syncErr != nil || closeErr != nil || n > MaxTransferUploadSize {
		_ = os.Remove(tempPath)
		_ = s.deleteJob(job.ID)
		if copyErr != nil {
			return nil, fmt.Errorf("save uploaded archive: %w", copyErr)
		}
		if n > MaxTransferUploadSize {
			return nil, fmt.Errorf("archive exceeds %d byte limit", MaxTransferUploadSize)
		}
		return nil, errors.Join(srcCloseErr, syncErr, closeErr)
	}
	if err := os.Rename(tempPath, archivePath); err != nil {
		_ = os.Remove(tempPath)
		_ = s.deleteJob(job.ID)
		return nil, fmt.Errorf("publish uploaded archive: %w", err)
	}
	if err := s.updateJob(job.ID, func(j *TransferJob) { j.uploadPath = archivePath }); err != nil {
		_ = os.Remove(archivePath)
		_ = s.deleteJob(job.ID)
		return nil, err
	}
	job.uploadPath = archivePath
	job.Stage = "queued"
	s.enqueue(job.ID)
	queued = true
	return job, nil
}

func (s *TransferService) claimTransfer() (string, error) {
	reservation := uuid.NewString()
	s.activeTransferMu.Lock()
	defer s.activeTransferMu.Unlock()
	if s.activeTransferID != "" {
		return "", ErrTransferInProgress
	}
	s.activeTransferID = reservation
	return reservation, nil
}

func (s *TransferService) bindTransfer(reservation, jobID string) {
	s.activeTransferMu.Lock()
	defer s.activeTransferMu.Unlock()
	if s.activeTransferID == reservation {
		s.activeTransferID = jobID
	}
}

func (s *TransferService) releaseTransfer(id string) {
	s.activeTransferMu.Lock()
	defer s.activeTransferMu.Unlock()
	if s.activeTransferID == id {
		s.activeTransferID = ""
	}
}

func (s *TransferService) ActiveImport(bookID string) (*TransferJob, error) {
	row := s.db.QueryRow(
		`SELECT id, book_id, type, status, stage, progress, error_msg, upload_path,
		        target_file_name, source_title, preview_json, created_at, updated_at
		 FROM transfer_jobs WHERE book_id = ? AND type = ? AND status IN (?, ?, ?)
		 ORDER BY created_at DESC LIMIT 1`,
		bookID, TransferTypeImport, TransferStatusPending, TransferStatusProcessing, TransferStatusAwaitingConfirmation,
	)
	var job TransferJob
	if err := row.Scan(
		&job.ID, &job.BookID, &job.Type, &job.Status, &job.Stage, &job.Progress,
		&job.ErrorMsg, &job.uploadPath, &job.TargetFileName, &job.SourceTitle,
		&job.Preview, &job.CreatedAt, &job.UpdatedAt,
	); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &job, nil
}

func (s *TransferService) deleteJob(id string) error {
	_, err := s.db.Exec(`DELETE FROM transfer_jobs WHERE id = ?`, id)
	return err
}

func (s *TransferService) createJob(bookID, kind, uploadPath string) (*TransferJob, error) {
	id := uuid.NewString()
	now := time.Now().UTC().Format(time.RFC3339Nano)
	job := &TransferJob{
		ID: id, BookID: bookID, Type: kind, Status: TransferStatusPending,
		Stage: "queued", uploadPath: uploadPath, CreatedAt: now, UpdatedAt: now,
	}
	_, err := s.db.Exec(
		`INSERT INTO transfer_jobs
		 (id, book_id, type, status, stage, progress, error_msg, upload_path, target_file_name,
		  source_title, preview_json, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, 0, '', ?, '', '', '{}', ?, ?)`,
		job.ID, job.BookID, job.Type, job.Status, job.Stage, job.uploadPath, now, now,
	)
	if err != nil {
		return nil, fmt.Errorf("create transfer job: %w", err)
	}
	return job, nil
}

func (s *TransferService) Get(id string) (*TransferJob, error) {
	row := s.db.QueryRow(
		`SELECT id, book_id, type, status, stage, progress, error_msg, upload_path,
		        target_file_name, source_title, preview_json, created_at, updated_at
		 FROM transfer_jobs WHERE id = ?`, id)
	var job TransferJob
	if err := row.Scan(
		&job.ID, &job.BookID, &job.Type, &job.Status, &job.Stage, &job.Progress,
		&job.ErrorMsg, &job.uploadPath, &job.TargetFileName, &job.SourceTitle,
		&job.Preview, &job.CreatedAt, &job.UpdatedAt,
	); err != nil {
		return nil, err
	}
	return &job, nil
}

func (s *TransferService) ConfirmImport(id string) (*TransferJob, error) {
	job, err := s.Get(id)
	if err != nil {
		return nil, err
	}
	if job.Type != TransferTypeImport || job.Status != TransferStatusAwaitingConfirmation {
		return nil, errors.New("transfer job is not awaiting confirmation")
	}
	if err := s.updateJob(id, func(j *TransferJob) {
		j.Status = TransferStatusPending
		j.Stage = "queued"
		j.Progress = 0
	}); err != nil {
		return nil, err
	}
	job, err = s.Get(id)
	if err == nil {
		s.enqueue(id)
	}
	return job, err
}

func (s *TransferService) CancelImport(id string) (*TransferJob, error) {
	job, err := s.Get(id)
	if err != nil {
		return nil, err
	}
	if job.Type != TransferTypeImport || job.Status != TransferStatusAwaitingConfirmation {
		return nil, errors.New("only an import awaiting confirmation can be canceled")
	}
	if err := s.updateJob(id, func(j *TransferJob) {
		j.Status = TransferStatusCanceled
		j.Stage = "canceled"
		j.Progress = 100
	}); err != nil {
		return nil, err
	}
	if err := os.Remove(job.uploadPath); err != nil && !errors.Is(err, os.ErrNotExist) {
		s.releaseTransfer(id)
		return nil, fmt.Errorf("remove canceled import archive: %w", err)
	}
	s.releaseTransfer(id)
	return s.Get(id)
}

func (s *TransferService) runJob(id string) error {
	job, err := s.Get(id)
	if err != nil {
		return err
	}
	if job.Status != TransferStatusPending {
		return nil
	}
	if err := s.updateJob(id, func(j *TransferJob) {
		j.Status = TransferStatusProcessing
		j.Stage = "starting"
		j.Progress = 1
		j.ErrorMsg = ""
	}); err != nil {
		return err
	}

	switch job.Type {
	case TransferTypeExport:
		err = s.runExport(job)
	case TransferTypeImport:
		if job.Preview == "" {
			err = s.runImportPreview(job)
		} else {
			err = s.runImport(job)
		}
	default:
		err = fmt.Errorf("unsupported transfer type %q", job.Type)
	}
	if err != nil {
		if updateErr := s.updateJob(id, func(j *TransferJob) {
			j.Status = TransferStatusFailed
			j.Stage = "failed"
			j.ErrorMsg = err.Error()
		}); updateErr != nil {
			return errors.Join(err, fmt.Errorf("mark transfer task failed: %w", updateErr))
		}
		s.releaseTransfer(id)
		return err
	}
	if job.Type == TransferTypeExport || job.Preview != "" {
		s.releaseTransfer(id)
	}
	return nil
}

func (s *TransferService) runExport(job *TransferJob) error {
	book, err := s.books.GetBook(job.BookID)
	if err != nil {
		return fmt.Errorf("load book for export: %w", err)
	}
	chapters, err := s.books.ListChapters(job.BookID)
	if err != nil {
		return fmt.Errorf("load chapters for export: %w", err)
	}
	tempPath := filepath.Join(s.exportDir, "."+job.ID+".part")
	targetPath := filepath.Join(s.exportDir, job.TargetFileName)
	_ = os.Remove(tempPath)
	_ = os.Remove(targetPath)
	if err := s.updateJob(job.ID, func(j *TransferJob) {
		j.Stage = "packaging"
		j.Progress = 5
	}); err != nil {
		return err
	}
	vectorCount, err := writeBookArchive(tempPath, *book, chapters, s.worker, func(count int) {
		progress := 5
		if count > 0 {
			progress = 5 + min(85, count/100)
		}
		_ = s.updateJob(job.ID, func(j *TransferJob) {
			j.Stage = "writing_vectors"
			j.Progress = progress
		})
	})
	if err != nil {
		_ = os.Remove(tempPath)
		return err
	}
	hasChapterData := false
	for _, chapter := range chapters {
		if chapter.Summary != "" || chapter.Keywords != "[]" || chapter.Definitions != "[]" {
			hasChapterData = true
			break
		}
	}
	var keywords []json.RawMessage
	if err := json.Unmarshal([]byte(book.Keywords), &keywords); err != nil {
		_ = os.Remove(tempPath)
		return fmt.Errorf("decode book keywords: %w", err)
	}
	if vectorCount == 0 && book.Summary == "" && len(keywords) == 0 && !hasChapterData {
		_ = os.Remove(tempPath)
		return errors.New("book has no exportable derived data")
	}
	if err := s.updateJob(job.ID, func(j *TransferJob) {
		j.Stage = "finalizing"
		j.Progress = 95
	}); err != nil {
		_ = os.Remove(tempPath)
		return err
	}
	if err := os.Rename(tempPath, targetPath); err != nil {
		_ = os.Remove(tempPath)
		return fmt.Errorf("publish export archive: %w", err)
	}
	if err := s.updateJob(job.ID, func(j *TransferJob) {
		j.Status = TransferStatusCompleted
		j.Stage = "completed"
		j.Progress = 100
	}); err != nil {
		return err
	}
	return nil
}

func (s *TransferService) runImportPreview(job *TransferJob) error {
	opened, err := openBookArchive(job.uploadPath)
	if err != nil {
		return err
	}
	defer opened.Close()
	book, err := s.books.GetBook(job.BookID)
	if err != nil {
		return fmt.Errorf("load target book: %w", err)
	}
	targetChapters, err := s.books.ListChapters(job.BookID)
	if err != nil {
		return fmt.Errorf("load target chapters: %w", err)
	}
	chapterMatches := matchChapters(opened.chapters, targetChapters)
	targetChunks, err := s.allBookChunks(job.BookID)
	if err != nil {
		return err
	}
	chunkMatches := indexTargetChunks(targetChunks)
	matchedVectors := 0
	vectorCount := 0
	chaptersByID := chapterIndex(opened.chapters)
	seenVectorIDs := make(map[string]struct{})
	dimension := opened.manifest.EmbeddingDim
	err = opened.vectorRecords(func(vector archiveVector) error {
		if dimension == 0 {
			dimension = len(vector.Embedding)
		}
		if err := validateVectorRecord(vector, dimension, chaptersByID); err != nil {
			return err
		}
		if vector.BookID != opened.book.SourceBookID {
			return fmt.Errorf("vector %q has an unexpected source book id", vector.ID)
		}
		if _, duplicate := seenVectorIDs[vector.ID]; duplicate {
			return fmt.Errorf("duplicate vector id %q", vector.ID)
		}
		seenVectorIDs[vector.ID] = struct{}{}
		vectorCount++
		if vectorTargetID(vector, opened, chapterMatches, chunkMatches, job.BookID) != "" {
			matchedVectors++
		}
		return nil
	})
	if err != nil {
		return err
	}
	if vectorCount != opened.manifest.VectorCount {
		return fmt.Errorf("vector count mismatch: manifest says %d, archive has %d", opened.manifest.VectorCount, vectorCount)
	}
	if dimension != opened.manifest.EmbeddingDim {
		return fmt.Errorf("embedding dimension mismatch: manifest says %d, archive has %d", opened.manifest.EmbeddingDim, dimension)
	}
	if opened.manifest.EmbeddingDim > 0 && vectorCount == 0 {
		return errors.New("manifest declares an embedding dimension but contains no vectors")
	}
	exact := opened.manifest.Fingerprint == bookFingerprint(book.Title, targetChapters)
	preview := TransferPreview{
		SourceTitle: opened.book.Title, TargetTitle: book.Title,
		SourceChapters: len(opened.chapters), MatchedChapters: len(chapterMatches),
		SourceVectors: vectorCount, MatchedVectors: matchedVectors, ExactBookMatch: exact,
	}
	if !exact || len(chapterMatches) != len(opened.chapters) || matchedVectors != vectorCount {
		preview.Warning = "partial_match"
	}
	previewJSON, err := json.Marshal(preview)
	if err != nil {
		return err
	}
	if err := s.updateJob(job.ID, func(j *TransferJob) {
		j.Status = TransferStatusAwaitingConfirmation
		j.Stage = "awaiting_confirmation"
		j.Progress = 100
		j.SourceTitle = opened.book.Title
		j.Preview = string(previewJSON)
	}); err != nil {
		return err
	}
	return nil
}

func (s *TransferService) runImport(job *TransferJob) error {
	opened, err := openBookArchive(job.uploadPath)
	if err != nil {
		return err
	}
	defer opened.Close()
	if _, err := s.books.GetBook(job.BookID); err != nil {
		return fmt.Errorf("load target book: %w", err)
	}
	targetChapters, err := s.books.ListChapters(job.BookID)
	if err != nil {
		return fmt.Errorf("load target chapters: %w", err)
	}
	chapterMatches := matchChapters(opened.chapters, targetChapters)
	chunkMatches, err := s.allBookChunks(job.BookID)
	if err != nil {
		return err
	}
	chunkIndex := indexTargetChunks(chunkMatches)
	stagingBookID := "stage-" + job.ID
	backupBookID := "backup-" + job.ID
	if err := s.updateJob(job.ID, func(j *TransferJob) {
		j.Stage = "staging_vectors"
		j.Progress = 5
	}); err != nil {
		return err
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	expectedDimension := 0
	vectorCount := 0
	err = s.worker.ImportBookVectors(ctx, func(send func(coordinator.VectorRecord) error) error {
		// Keep vectors that exist on the target device but do not match the
		// source package, then overlay only vectors whose text/chapter mapping
		// is verified.
		if err := s.worker.ExportBookVectors(job.BookID, func(current coordinator.VectorRecord) error {
			if expectedDimension == 0 {
				expectedDimension = len(current.Embedding)
			} else if len(current.Embedding) != expectedDimension {
				return errors.New("target book has inconsistent embedding dimensions")
			}
			current.BookID = stagingBookID
			vectorCount++
			return send(current)
		}); err != nil {
			return fmt.Errorf("stage target vectors: %w", err)
		}

		chaptersByID := chapterIndex(opened.chapters)
		return opened.vectorRecords(func(record archiveVector) error {
			if err := validateVectorRecord(record, opened.manifest.EmbeddingDim, chaptersByID); err != nil {
				return err
			}
			targetID := vectorTargetID(record, opened, chapterMatches, chunkIndex, job.BookID)
			if targetID == "" {
				return nil
			}
			if expectedDimension == 0 {
				expectedDimension = len(record.Embedding)
			} else if len(record.Embedding) != expectedDimension {
				return fmt.Errorf("vector %q embedding dimension does not match the target index", record.ID)
			}
			targetChapterID := chapterMatches[record.ChapterID]
			if strings.HasSuffix(record.ID, ":summary") && record.ChapterID != "" {
				targetID = targetChapterID + ":summary"
			}
			if strings.HasSuffix(record.ID, ":summary") && record.ChapterID == "" {
				targetID = job.BookID + ":summary"
			}
			if err := send(coordinator.VectorRecord{
				ID: targetID, BookID: stagingBookID, ChapterID: targetChapterID, Content: record.Content,
				Position: record.Position, TokenCount: record.TokenCount, StartOffset: record.StartOffset,
				EndOffset: record.EndOffset, Embedding: record.Embedding,
			}); err != nil {
				return err
			}
			vectorCount++
			if vectorCount%transferBatchSize == 0 {
				progress := 10 + min(70, vectorCount/100)
				_ = s.updateJob(job.ID, func(j *TransferJob) { j.Progress = progress })
			}
			return nil
		})
	})
	if err != nil {
		_ = s.worker.DeleteBook(stagingBookID)
		return fmt.Errorf("stage imported vectors: %w", err)
	}

	if err := s.updateJob(job.ID, func(j *TransferJob) {
		j.Stage = "committing"
		j.Progress = 85
	}); err != nil {
		_ = s.worker.DeleteBook(stagingBookID)
		return err
	}
	tx, err := s.db.Begin()
	if err != nil {
		_ = s.worker.DeleteBook(stagingBookID)
		return fmt.Errorf("begin derived-data transaction: %w", err)
	}
	rollbackSQL := true
	defer func() {
		if rollbackSQL {
			_ = tx.Rollback()
		}
	}()
	if _, err := tx.Exec(`UPDATE books SET summary = ?, keywords = ?, updated_at = ? WHERE id = ?`,
		opened.book.Summary, string(validJSONOr(string(opened.book.Keywords), "[]")),
		time.Now().UTC().Format(time.RFC3339Nano), job.BookID); err != nil {
		_ = s.worker.DeleteBook(stagingBookID)
		return fmt.Errorf("update imported book summary: %w", err)
	}
	for sourceID, targetID := range chapterMatches {
		var source *archiveChapter
		for i := range opened.chapters {
			if opened.chapters[i].ID == sourceID {
				source = &opened.chapters[i]
				break
			}
		}
		if source == nil {
			continue
		}
		if _, err := tx.Exec(
			`UPDATE chapters SET summary = ?, keywords = ?, definitions = ? WHERE id = ? AND book_id = ?`,
			source.Summary, string(validJSONOr(string(source.Keywords), "[]")),
			string(validJSONOr(string(source.Definitions), "[]")), targetID, job.BookID,
		); err != nil {
			_ = s.worker.DeleteBook(stagingBookID)
			return fmt.Errorf("update imported chapter summary: %w", err)
		}
	}
	if err := s.worker.CommitBookVectorImport(job.BookID, stagingBookID, backupBookID); err != nil {
		return fmt.Errorf("commit imported vectors: %w", err)
	}
	if err := tx.Commit(); err != nil {
		rollbackSQL = false
		_ = s.worker.RollbackBookVectorImport(job.BookID, stagingBookID, backupBookID)
		return fmt.Errorf("commit imported book data: %w", err)
	}
	rollbackSQL = false
	if err := s.updateJob(job.ID, func(j *TransferJob) {
		j.Status = TransferStatusCompleted
		j.Stage = "completed"
		j.Progress = 100
	}); err != nil {
		return err
	}
	if err := s.worker.FinalizeBookVectorImport(stagingBookID, backupBookID); err != nil {
		log.Printf("transfer task %s completed; failed to remove vector import backup: %v", job.ID, err)
	}
	if err := os.Remove(job.uploadPath); err != nil && !errors.Is(err, os.ErrNotExist) {
		log.Printf("transfer task %s completed; failed to remove uploaded archive: %v", job.ID, err)
	}
	return nil
}

func (s *TransferService) allBookChunks(bookID string) ([]models.Chunk, error) {
	var result []models.Chunk
	for page := 1; ; page++ {
		chunks, total, err := s.books.ListChunks(bookID, "", page, 500)
		if err != nil {
			return nil, fmt.Errorf("load target chunks: %w", err)
		}
		result = append(result, chunks...)
		if len(result) >= int(total) || len(chunks) == 0 {
			return result, nil
		}
	}
}

func (s *TransferService) updateJob(id string, update func(*TransferJob)) error {
	job, err := s.Get(id)
	if err != nil {
		return err
	}
	update(job)
	job.UpdatedAt = time.Now().UTC().Format(time.RFC3339Nano)
	_, err = s.db.Exec(
		`UPDATE transfer_jobs SET status = ?, stage = ?, progress = ?, error_msg = ?, upload_path = ?,
		 target_file_name = ?, source_title = ?, preview_json = ?, updated_at = ? WHERE id = ?`,
		job.Status, job.Stage, job.Progress, job.ErrorMsg, job.uploadPath, job.TargetFileName,
		job.SourceTitle, job.Preview, job.UpdatedAt, job.ID,
	)
	if err != nil {
		return fmt.Errorf("update transfer job: %w", err)
	}
	return nil
}

func matchChapters(source []archiveChapter, target []models.Chapter) map[string]string {
	type matchKey struct{ title, hash string }
	targets := make(map[matchKey][]string)
	for _, chapter := range target {
		key := matchKey{strings.TrimSpace(chapter.Title), contentHash(chapter.Content)}
		targets[key] = append(targets[key], chapter.ID)
	}
	for key := range targets {
		sort.Strings(targets[key])
	}
	result := make(map[string]string)
	for _, chapter := range source {
		key := matchKey{strings.TrimSpace(chapter.Title), chapter.ContentHash}
		matches := targets[key]
		if len(matches) == 0 {
			continue
		}
		result[chapter.ID] = matches[0]
		targets[key] = matches[1:]
	}
	return result
}

func chapterIndex(chapters []archiveChapter) map[string]struct{} {
	index := make(map[string]struct{}, len(chapters))
	for _, chapter := range chapters {
		index[chapter.ID] = struct{}{}
	}
	return index
}

type chunkMatchKey struct {
	chapterID   string
	position    int
	contentHash string
}

func indexTargetChunks(chunks []models.Chunk) map[chunkMatchKey]string {
	result := make(map[chunkMatchKey]string, len(chunks))
	for _, chunk := range chunks {
		key := chunkMatchKey{
			chapterID: chunk.ChapterID, position: chunk.Position, contentHash: contentHash(chunk.Content),
		}
		result[key] = chunk.ID
	}
	return result
}

func vectorTargetID(
	record archiveVector,
	archive *openedArchive,
	chapterMatches map[string]string,
	chunkMatches map[chunkMatchKey]string,
	targetBookID string,
) string {
	if record.ID == archive.book.SourceBookID+":summary" && record.ChapterID == "" {
		return targetBookID + ":summary"
	}
	if strings.HasSuffix(record.ID, ":summary") && record.ChapterID != "" {
		if chapterID := chapterMatches[record.ChapterID]; chapterID != "" {
			return chapterID + ":summary"
		}
		return ""
	}
	targetChapterID := chapterMatches[record.ChapterID]
	if targetChapterID == "" {
		return ""
	}
	return chunkMatches[chunkMatchKey{
		chapterID: targetChapterID, position: record.Position, contentHash: contentHash(record.Content),
	}]
}

func validateArchiveVectors(archive *openedArchive) (int, error) {
	chapters := chapterIndex(archive.chapters)
	seen := make(map[string]struct{})
	count := 0
	dimension := archive.manifest.EmbeddingDim
	err := archive.vectorRecords(func(record archiveVector) error {
		if err := validateVectorRecord(record, dimension, chapters); err != nil {
			return err
		}
		if record.BookID != archive.book.SourceBookID {
			return fmt.Errorf("vector %q has an unexpected source book id", record.ID)
		}
		if _, duplicate := seen[record.ID]; duplicate {
			return fmt.Errorf("duplicate vector id %q", record.ID)
		}
		seen[record.ID] = struct{}{}
		if dimension == 0 {
			dimension = len(record.Embedding)
		}
		count++
		return nil
	})
	if err != nil {
		return count, err
	}
	if count != archive.manifest.VectorCount {
		return count, fmt.Errorf("vector count mismatch: manifest says %d, archive has %d", archive.manifest.VectorCount, count)
	}
	return count, nil
}

func archiveEntryByName(reader *zip.ReadCloser, name string) (*zip.File, error) {
	for _, file := range reader.File {
		if file.Name == name {
			return file, nil
		}
	}
	return nil, fmt.Errorf("archive entry %q not found", name)
}

func copyArchiveEntry(dst io.Writer, file *zip.File) error {
	src, err := file.Open()
	if err != nil {
		return err
	}
	defer src.Close()
	_, err = io.Copy(dst, src)
	return err
}

func writeHashedEntry(writer *zip.Writer, name string) (io.Writer, hash.Hash, error) {
	entry, err := writer.Create(name)
	if err != nil {
		return nil, nil, err
	}
	digest := sha256.New()
	return io.MultiWriter(entry, digest), digest, nil
}

func decodeJSONLines[T any](reader io.Reader, consume func(T) error) error {
	scanner := bufio.NewScanner(reader)
	scanner.Buffer(make([]byte, 64*1024), 16*1024*1024)
	for scanner.Scan() {
		var record T
		if err := json.Unmarshal(scanner.Bytes(), &record); err != nil {
			return err
		}
		if err := consume(record); err != nil {
			return err
		}
	}
	return scanner.Err()
}
