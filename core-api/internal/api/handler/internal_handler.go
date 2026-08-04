package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

// InternalHandler serves the callbacks Worker posts back to while running a
// task (see docs/系统设计文档.md §2.3). Not exposed under /api/v1, and not
// authenticated yet — Core API and Worker only talk over the Docker-internal
// network in the current deployment model.
type InternalHandler struct {
	books *service.BookService
	tasks *service.TaskService
}

func NewInternalHandler(books *service.BookService, tasks *service.TaskService) *InternalHandler {
	return &InternalHandler{books: books, tasks: tasks}
}

func (h *InternalHandler) Progress(c *gin.Context) {
	taskID := c.Param("id")

	var req dto.TaskProgressCallback
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	task, err := h.tasks.GetTask(taskID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}

	if err := h.tasks.UpdateProgress(taskID, req.Progress); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := h.books.SetStatus(task.BookID, models.BookStatusProcessing); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"ok": true})
}

func (h *InternalHandler) Complete(c *gin.Context) {
	taskID := c.Param("id")

	var req dto.TaskCompleteCallback
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	task, err := h.tasks.GetTask(taskID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}

	chapters := make([]service.ParsedChapter, 0, len(req.Chapters))
	for _, ch := range req.Chapters {
		chapters = append(chapters, service.ParsedChapter{
			ID: ch.ID, Title: ch.Title, Level: ch.Level, SortOrder: ch.SortOrder, Content: ch.Content,
		})
	}
	if err := h.books.SaveChapters(task.BookID, chapters); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	chunks := make([]service.ParsedChunk, 0, len(req.Chunks))
	for _, ch := range req.Chunks {
		chunks = append(chunks, service.ParsedChunk{
			ID: ch.ID, ChapterID: ch.ChapterID, Content: ch.Content,
			Position: ch.Position, TokenCount: ch.TokenCount, VectorID: ch.VectorID,
		})
	}
	if err := h.books.SaveChunks(task.BookID, chunks); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if err := h.books.ApplyParsedMetadata(task.BookID, req.Book.Title, req.Book.Author, req.Book.Language); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := h.books.SetStatus(task.BookID, models.BookStatusReady); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := h.tasks.Complete(taskID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"ok": true})
}

func (h *InternalHandler) Fail(c *gin.Context) {
	taskID := c.Param("id")

	var req dto.TaskFailCallback
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	task, err := h.tasks.GetTask(taskID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}

	if err := h.tasks.Fail(taskID, req.ErrorMsg); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := h.books.SetStatus(task.BookID, models.BookStatusFailed); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"ok": true})
}
