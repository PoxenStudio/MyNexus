package handler

import (
	"encoding/json"
	"net/http"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

var supportedFormats = map[string]bool{".epub": true, ".txt": true}

// defaultUserID stands in for the not-yet-implemented auth system (see M1/M2
// scope notes in docs/开发技术文档.md §15): every book is owned by this user
// until API Token / JWT auth lands.
const defaultUserID = "local-user"

type BookHandler struct {
	books  *service.BookService
	tasks  *service.TaskService
	worker *coordinator.WorkerClient
	audit  *service.AuditService
	cfg    config.Config
}

func NewBookHandler(cfg config.Config, books *service.BookService, tasks *service.TaskService, worker *coordinator.WorkerClient, audit *service.AuditService) *BookHandler {
	return &BookHandler{books: books, tasks: tasks, worker: worker, audit: audit, cfg: cfg}
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

	filePath, err := h.books.SaveUploadedFile(book.ID, fileHeader)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	task, err := h.tasks.CreateTask(book.ID, defaultUserID, models.TaskTypeIngest)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if err := h.worker.TriggerIngest(coordinator.IngestRequest{
		TaskID:           task.ID,
		BookID:           book.ID,
		FilePath:         filePath,
		OriginalFilename: filepath.Base(fileHeader.Filename),
		CallbackBaseURL:  h.cfg.Server.InternalURL,
	}); err != nil {
		_ = h.tasks.Fail(task.ID, "failed to reach worker: "+err.Error())
		_ = h.books.SetStatus(book.ID, models.BookStatusFailed)
		c.JSON(http.StatusBadGateway, gin.H{"error": "failed to trigger ingestion: " + err.Error()})
		return
	}

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
		items = append(items, dto.NewBookResponse(b))
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
		BookResponse: dto.NewBookResponse(*book),
		Chapters:     chapterResponses,
	})
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
	if err := h.books.UpdateBook(id, req.Title, req.Author, req.Category, string(tagsJSON)); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	book, _ := h.books.GetBook(id)
	c.JSON(http.StatusOK, dto.NewBookResponse(*book))
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
	if actor, ok := c.Get("actor"); ok {
		title := ""
		if book != nil {
			title = book.Title
		}
		_ = h.audit.Log(actor.(string), "book.delete", "book", id, title)
	}
	c.Status(http.StatusNoContent)
}
