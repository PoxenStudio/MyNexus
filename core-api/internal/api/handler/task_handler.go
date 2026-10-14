package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/dispatch"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

type TaskHandler struct {
	tasks      *service.TaskService
	books      *service.BookService
	worker     *coordinator.WorkerClient
	dispatcher *dispatch.Dispatcher
	audit      *service.AuditService
	cfg        config.Config
}

func NewTaskHandler(cfg config.Config, tasks *service.TaskService, books *service.BookService, worker *coordinator.WorkerClient, dispatcher *dispatch.Dispatcher, audit *service.AuditService) *TaskHandler {
	return &TaskHandler{tasks: tasks, books: books, worker: worker, dispatcher: dispatcher, audit: audit, cfg: cfg}
}

func (h *TaskHandler) List(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	size, _ := strconv.Atoi(c.DefaultQuery("size", "20"))
	status := c.Query("status")
	bookID := c.Query("book_id")

	tasks, total, err := h.tasks.ListTasks(page, size, status, bookID)
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
				ID: ch.ID, Title: ch.Title, Level: ch.Level, Content: ch.Content, Summary: ch.Summary,
			})
		}
		// Retry resumes rather than restarts: chapters already summarized
		// before the failure are kept, only the missing ones are redone.
		if err := h.worker.TriggerSummarize(coordinator.SummarizeRequest{
			TaskID: id, BookID: book.ID, Chapters: reqChapters, ForceRestart: false,
		}); err != nil {
			_ = h.tasks.Fail(id, err.Error())
			c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
			return
		}
	} else {
		// Queued, not necessarily dispatched yet — same as a freshly
		// created ingest task (see BookHandler.Import/rebuildOne):
		// TaskService.Retry already reset dispatched_at to NULL, so this
		// goes through the concurrency-capped queue rather than bypassing
		// it. See internal/dispatch.Dispatcher.
		_ = h.books.SetStatus(book.ID, models.BookStatusPending)
		h.dispatcher.TryDispatch()
	}

	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "task.retry", "task", id, "book_id="+book.ID)
	}
	c.JSON(http.StatusAccepted, dto.NewTaskResponse(*task))
}

// Cancel asks Worker to interrupt a running task (currently only summarize
// runs honor the flag — see worker's CancelTask). Only pending/processing
// tasks can be cancelled. When Worker confirms it set the cancel flag the
// task stays processing until Worker actually stops and reports back
// ReportFail(canceled=true); when Worker has no such active run (never
// dispatched, or Worker unreachable/restarted) the task is marked canceled
// directly since nothing is running that would ever report.
func (h *TaskHandler) Cancel(c *gin.Context) {
	id := c.Param("id")
	task, err := h.tasks.GetTask(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}
	if task.Status != models.TaskStatusPending && task.Status != models.TaskStatusProcessing {
		c.JSON(http.StatusConflict, gin.H{"error": "task is not running"})
		return
	}

	markCanceled := func() {
		if err := h.tasks.Cancel(id); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		if actor, ok := c.Get("actor"); ok {
			_ = h.audit.Log(actor.(string), "task.cancel", "task", id, "book_id="+task.BookID)
		}
		updated, err := h.tasks.GetTask(id)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusAccepted, dto.NewTaskResponse(*updated))
	}

	if task.DispatchedAt == "" {
		markCanceled()
		return
	}
	found, err := h.worker.CancelTask(id)
	if err != nil || !found {
		markCanceled()
		return
	}

	if actor, ok := c.Get("actor"); ok {
		_ = h.audit.Log(actor.(string), "task.cancel", "task", id, "book_id="+task.BookID)
	}
	c.JSON(http.StatusAccepted, dto.NewTaskResponse(*task))
}
