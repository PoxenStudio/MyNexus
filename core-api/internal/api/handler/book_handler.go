package handler

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/dispatch"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

var supportedFormats = map[string]bool{".epub": true, ".txt": true}

// defaultUserID stands in for the not-yet-implemented auth system (see M1/M2
// scope notes in docs/开发技术文档.md §15): every book is owned by this user
// until API Token / JWT auth lands.
const defaultUserID = "local-user"

type BookHandler struct {
	books      *service.BookService
	tasks      *service.TaskService
	worker     *coordinator.WorkerClient
	dispatcher *dispatch.Dispatcher
	audit      *service.AuditService
	cfg        config.Config
}

func NewBookHandler(cfg config.Config, books *service.BookService, tasks *service.TaskService, worker *coordinator.WorkerClient, dispatcher *dispatch.Dispatcher, audit *service.AuditService) *BookHandler {
	return &BookHandler{books: books, tasks: tasks, worker: worker, dispatcher: dispatcher, audit: audit, cfg: cfg}
}

func (h *BookHandler) Import(c *gin.Context) {
	fileHeader, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "file is required"})
		return
	}

	ext := strings.ToLower(filepath.Ext(fileHeader.Filename))
	if !supportedFormats[ext] {
		c.JSON(http.StatusBadRequest, gin.H{"error": "unsupported file format: " + ext})
		return
	}

	sourceOrigin := c.PostForm("source_origin")
	if sourceOrigin == "" {
		sourceOrigin = models.SourceOriginDirectUpload
	}

	book, err := h.books.CreateBook(defaultUserID, strings.TrimPrefix(ext, "."), sourceOrigin)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// The dispatcher (below) reads the saved path back off the book row
	// itself when it actually dispatches, rather than needing it threaded
	// through here.
	if _, err := h.books.SaveUploadedFile(book.ID, fileHeader); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// cover_url: optional, for callers that already know a cover image URL
	// for this book (e.g. MyBooks' own cover endpoint — see
	// docs/系统设计文档.md's import-url design note). Downloaded to local
	// storage right here, synchronously, rather than stored as a URL and
	// fetched on demand later — the source system isn't guaranteed to still
	// be reachable whenever a user opens this book's page afterwards.
	// Best-effort: a failed download just leaves the book without a cover
	// yet, to be filled in by Worker's EPUB-extraction/title-generation
	// fallback at ingest completion (see grpcserver.ReportComplete) — it
	// never fails the import itself.
	if coverURL := c.PostForm("cover_url"); coverURL != "" {
		if _, err := h.books.DownloadCover(book.ID, coverURL); err != nil {
			log.Printf("book %s: failed to download cover from %s: %v", book.ID, coverURL, err)
		}
	}

	task, err := h.tasks.CreateTask(book.ID, defaultUserID, models.TaskTypeIngest)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	// Queued, not necessarily dispatched yet — TryDispatch hands it to
	// Worker right away if there's a free worker.max_concurrent_tasks slot,
	// otherwise it's left queued (see internal/dispatch.Dispatcher) and
	// picked up automatically once one frees up. Either way this is a
	// successful import from the caller's point of view: the file is saved
	// and the task exists, so there's nothing to report as failed here even
	// if Worker happens to be unreachable right now.
	h.dispatcher.TryDispatch()

	c.JSON(http.StatusAccepted, dto.ImportResponse{TaskID: task.ID, BookID: book.ID})
}

func (h *BookHandler) List(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	size, _ := strconv.Atoi(c.DefaultQuery("size", "20"))
	status := c.Query("status")
	q := c.Query("q")

	books, total, err := h.books.ListBooks(page, size, status, q)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	items := make([]dto.BookResponse, 0, len(books))
	for _, b := range books {
		items = append(items, dto.NewBookResponse(b, h.cfg.Keyword.MaxKeywords))
	}
	c.JSON(http.StatusOK, dto.BookListResponse{Items: items, Total: total, Page: page, Size: size})
}

func (h *BookHandler) Get(c *gin.Context) {
	id := c.Param("id")
	book, err := h.books.GetBook(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "book not found"})
		return
	}

	chapters, err := h.books.ListChapters(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	chapterResponses := make([]dto.ChapterResponse, 0, len(chapters))
	for _, ch := range chapters {
		chapterResponses = append(chapterResponses, dto.NewChapterResponse(ch))
	}

	c.JSON(http.StatusOK, dto.BookDetailResponse{
		BookResponse: dto.NewBookResponse(*book, h.cfg.Keyword.MaxKeywords),
		Chapters:     chapterResponses,
	})
}

// Cover streams a book's cover image (see BookService's coverDir) — mirrors
// AuthHandler.ServeAvatar. 404 if the book has none yet (not-yet-ingested,
// ingested but Worker found/generated nothing, or the file was deleted from
// under us); BookDetailView.vue falls back to its own title-initial
// placeholder in that case (see its @error handler on the <img> tag).
func (h *BookHandler) Cover(c *gin.Context) {
	id := c.Param("id")
	book, err := h.books.GetBook(id)
	if err != nil || book.CoverPath == "" {
		c.Status(http.StatusNotFound)
		return
	}
	// Cache-Control: covers are effectively immutable once set (never
	// overwritten in place — Rebuild/ReportComplete only fill an empty
	// cover_path, they don't replace an existing one), so a long-lived
	// browser cache is safe.
	c.Header("Cache-Control", "public, max-age=604800")
	c.File(book.CoverPath)
}

func (h *BookHandler) Update(c *gin.Context) {
	id := c.Param("id")
	if _, err := h.books.GetBook(id); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "book not found"})
		return
	}

	var req dto.UpdateBookRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	tagsJSON, _ := json.Marshal(req.Tags)
	if err := h.books.UpdateBook(id, req.Title, req.Author, req.Category, req.Language, string(tagsJSON)); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	book, _ := h.books.GetBook(id)
	c.JSON(http.StatusOK, dto.NewBookResponse(*book, h.cfg.Keyword.MaxKeywords))
}

// UpdateSummary handles the book-detail page's "全书总结" edit box — a
// manual touch-up of the generated summary, distinct from Update (which
// covers title/author/category/tags/language) so a small wording fix can't
// accidentally clobber those in the same request.
func (h *BookHandler) UpdateSummary(c *gin.Context) {
	id := c.Param("id")
	if _, err := h.books.GetBook(id); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "book not found"})
		return
	}

	var req dto.UpdateBookSummaryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := h.books.UpdateBookSummary(id, req.Summary); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Best-effort: keep the summary's vector-store chunk in sync with this
	// edit (see worker/src/pipelines/summary.py's _index_summary — a
	// stable-id upsert, so this only re-embeds the one changed chunk, not
	// the whole book). The edit itself already succeeded above; a Worker
	// hiccup here just means retrieval keeps serving the previous summary
	// text until the next successful (re-)embed, not a failed request.
	if err := h.worker.ReembedBookSummary(id, req.Summary); err != nil {
		log.Printf("book %s: failed to reembed summary: %v", id, err)
	}

	book, _ := h.books.GetBook(id)
	c.JSON(http.StatusOK, dto.NewBookResponse(*book, h.cfg.Keyword.MaxKeywords))
}

func (h *BookHandler) Chunks(c *gin.Context) {
	id := c.Param("id")
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	size, _ := strconv.Atoi(c.DefaultQuery("size", "50"))
	chapterID := c.Query("chapter_id")

	chunks, total, err := h.books.ListChunks(id, chapterID, page, size)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	items := make([]dto.ChunkResponse, 0, len(chunks))
	for _, ch := range chunks {
		items = append(items, dto.NewChunkResponse(ch))
	}
	c.JSON(http.StatusOK, dto.ChunkListResponse{Items: items, Total: total, Page: page, Size: size})
}

func (h *BookHandler) Delete(c *gin.Context) {
	id := c.Param("id")
	book, _ := h.books.GetBook(id)
	if err := h.books.DeleteBook(id); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "book not found"})
		return
	}
	// Best-effort: Worker being unreachable shouldn't block the delete the
	// caller already got a success response for (same pattern as Shutdown in
	// system_handler.go). Otherwise the book's chunks would still be
	// retrievable/citable in chat with no matching books/chunks row to
	// resolve them against (see .claude/memory/mynexus_orphaned_vectors.md).
	go func() { _ = h.worker.DeleteBook(id) }()
	if actor, ok := c.Get("actor"); ok {
		title := ""
		if book != nil {
			title = book.Title
		}
		_ = h.audit.Log(actor.(string), "book.delete", "book", id, title)
	}
	c.Status(http.StatusNoContent)
}

// Rebuild re-submits a book's existing uploaded file to Worker for a fresh
// parse/split/embed pass (需求文档.md §6.7.3 "对单本书籍执行重新构建..."), creating
// a new task rather than reusing an old one — unlike task_handler.Retry (which
// only applies to an already-failed task), Rebuild works on any book that
// still has its original file on disk, regardless of current status (e.g.
// after changing the embedding model or chunk size on an already-"ready" book).
func (h *BookHandler) Rebuild(c *gin.Context) {
	id := c.Param("id")
	taskID, err := h.rebuildOne(id)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "book.rebuild", "book", id, "task_id="+taskID)
	}
	c.JSON(http.StatusAccepted, dto.RebuildResponse{TaskID: taskID, BookID: id})
}

func (h *BookHandler) rebuildOne(bookID string) (taskID string, err error) {
	book, err := h.books.GetBook(bookID)
	if err != nil {
		return "", err
	}
	if book.FilePath == "" {
		return "", fmt.Errorf("book has no stored file to rebuild from")
	}

	task, err := h.tasks.CreateTask(book.ID, defaultUserID, models.TaskTypeIngest)
	if err != nil {
		return "", err
	}
	_ = h.books.SetStatus(book.ID, models.BookStatusPending)

	// Queued, not necessarily dispatched yet — see the matching comment in
	// Import. BulkRebuild is exactly the bulk-trigger case
	// worker.max_concurrent_tasks exists to guard against: without the
	// dispatcher queue, selecting 20 books and clicking "批量重建" used to
	// fire 20 concurrent TriggerIngest calls at Worker regardless of this
	// setting.
	h.dispatcher.TryDispatch()
	return task.ID, nil
}

// Summarize triggers the map-reduce summarization pipeline (chapter
// summaries, then a whole-book summary — see worker/src/pipelines/summary.py)
// for an already-ingested book. Requires the book to have chapters (i.e. a
// completed ingest); re-running it (e.g. after editing/re-ingesting content)
// simply overwrites the previous summaries.
func (h *BookHandler) Summarize(c *gin.Context) {
	id := c.Param("id")
	// mode=continue resumes a partial run, only (re)generating chapters that
	// don't already have a summary; anything else (including the default,
	// no chapters summarized yet) restarts every chapter from scratch.
	forceRestart := c.Query("mode") != "continue"
	taskID, err := h.summarizeOne(id, forceRestart)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "book.summarize", "book", id, "task_id="+taskID)
	}
	c.JSON(http.StatusAccepted, dto.RebuildResponse{TaskID: taskID, BookID: id})
}

func (h *BookHandler) summarizeOne(bookID string, forceRestart bool) (taskID string, err error) {
	book, err := h.books.GetBook(bookID)
	if err != nil {
		return "", err
	}

	chapters, err := h.books.ListChapters(bookID)
	if err != nil {
		return "", err
	}
	if len(chapters) == 0 {
		return "", fmt.Errorf("book has no chapters to summarize (ingest it first)")
	}

	task, err := h.tasks.CreateTask(bookID, defaultUserID, models.TaskTypeSummarize)
	if err != nil {
		return "", err
	}

	reqChapters := make([]coordinator.SummarizeChapter, 0, len(chapters))
	for _, ch := range chapters {
		reqChapters = append(reqChapters, coordinator.SummarizeChapter{
			ID: ch.ID, Title: ch.Title, Level: ch.Level, Content: ch.Content, Summary: ch.Summary,
		})
	}

	if err := h.worker.TriggerSummarize(coordinator.SummarizeRequest{
		TaskID: task.ID, BookID: bookID, Chapters: reqChapters, ForceRestart: forceRestart,
		Language: book.Language,
	}); err != nil {
		_ = h.tasks.Fail(task.ID, "failed to reach worker: "+err.Error())
		return "", fmt.Errorf("failed to trigger summarization: %w", err)
	}
	return task.ID, nil
}

// BulkDelete and BulkRebuild implement 需求文档.md §6.7.3's "批量选择书籍并执行删除
// 或重建操作" — each book is processed independently so one failure (e.g. a
// book whose file was already removed from disk) doesn't block the rest;
// per-item results are returned so the UI can report exactly which ones failed.

func (h *BookHandler) BulkDelete(c *gin.Context) {
	var req dto.BulkBookRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "ids is required"})
		return
	}

	actor, _ := c.Get("actor")
	items := make([]dto.BulkResultItem, 0, len(req.IDs))
	for _, id := range req.IDs {
		if err := h.books.DeleteBook(id); err != nil {
			items = append(items, dto.BulkResultItem{ID: id, OK: false, Error: err.Error()})
			continue
		}
		go func(bookID string) { _ = h.worker.DeleteBook(bookID) }(id)
		items = append(items, dto.BulkResultItem{ID: id, OK: true})
	}
	if actor != nil {
		_ = h.audit.Log(actor.(string), "book.bulk_delete", "book", "", strings.Join(req.IDs, ","))
	}
	c.JSON(http.StatusOK, dto.BulkResultResponse{Items: items})
}

func (h *BookHandler) BulkRebuild(c *gin.Context) {
	var req dto.BulkBookRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "ids is required"})
		return
	}

	actor, _ := c.Get("actor")
	items := make([]dto.BulkResultItem, 0, len(req.IDs))
	for _, id := range req.IDs {
		if _, err := h.rebuildOne(id); err != nil {
			items = append(items, dto.BulkResultItem{ID: id, OK: false, Error: err.Error()})
			continue
		}
		items = append(items, dto.BulkResultItem{ID: id, OK: true})
	}
	if actor != nil {
		_ = h.audit.Log(actor.(string), "book.bulk_rebuild", "book", "", strings.Join(req.IDs, ","))
	}
	c.JSON(http.StatusOK, dto.BulkResultResponse{Items: items})
}
