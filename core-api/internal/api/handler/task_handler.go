package handler

import (
	"net/http"
	"path/filepath"
	"strconv"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

type TaskHandler struct {
	tasks  *service.TaskService
	books  *service.BookService
	worker *coordinator.WorkerClient
	audit  *service.AuditService
	cfg    config.Config
}

func NewTaskHandler(cfg config.Config, tasks *service.TaskService, books *service.BookService, worker *coordinator.WorkerClient, audit *service.AuditService) *TaskHandler {
	return &TaskHandler{tasks: tasks, books: books, worker: worker, audit: audit, cfg: cfg}
}

func (h *TaskHandler) List(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	size, _ := strconv.Atoi(c.DefaultQuery("size", "20"))
	status := c.Query("status")

	tasks, total, err := h.tasks.ListTasks(page, size, status)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	items := make([]dto.TaskResponse, 0, len(tasks))
	for _, t := range tasks {
		items = append(items, dto.NewTaskResponse(t))
	}
	c.JSON(http.StatusOK, dto.TaskListResponse{Items: items, Total: total, Page: page, Size: size})
}

func (h *TaskHandler) Get(c *gin.Context) {
	id := c.Param("id")
	task, err := h.tasks.GetTask(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}
	c.JSON(http.StatusOK, dto.NewTaskResponse(*task))
}

// Retry resets a failed task to pending and re-submits it to Worker — against
// the book's existing uploaded file for an ingest task (docs/开发技术文档.md
// §10.5 "失败任务重试"), or against its existing chapters for a summarize task.
func (h *TaskHandler) Retry(c *gin.Context) {
	id := c.Param("id")
	task, err := h.tasks.GetTask(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}
	book, err := h.books.GetBook(task.BookID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "book not found"})
		return
	}

	if err := h.tasks.Retry(id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if task.Type == models.TaskTypeSummarize {
		chapters, err := h.books.ListChapters(book.ID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		reqChapters := make([]coordinator.SummarizeChapter, 0, len(chapters))
		for _, ch := range chapters {
			reqChapters = append(reqChapters, coordinator.SummarizeChapter{
				ID: ch.ID, Title: ch.Title, Level: ch.Level, Content: ch.Content,
			})
		}
		if err := h.worker.TriggerSummarize(coordinator.SummarizeRequest{
			TaskID: id, BookID: book.ID, Chapters: reqChapters,
		}); err != nil {
			_ = h.tasks.Fail(id, "failed to reach worker: "+err.Error())
			c.JSON(http.StatusBadGateway, gin.H{"error": "failed to trigger summarization: " + err.Error()})
			return
		}
	} else {
		_ = h.books.SetStatus(book.ID, models.BookStatusPending)
		if err := h.worker.TriggerIngest(coordinator.IngestRequest{
			TaskID: id, BookID: book.ID, FilePath: book.FilePath,
			OriginalFilename: filepath.Base(book.FilePath),
		}); err != nil {
			_ = h.tasks.Fail(id, "failed to reach worker: "+err.Error())
			_ = h.books.SetStatus(book.ID, models.BookStatusFailed)
			c.JSON(http.StatusBadGateway, gin.H{"error": "failed to trigger ingestion: " + err.Error()})
			return
		}
	}

	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "task.retry", "task", id, "book_id="+book.ID)
	}
	c.JSON(http.StatusAccepted, dto.NewTaskResponse(*task))
}
