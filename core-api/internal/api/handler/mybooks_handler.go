package handler

import (
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/dispatch"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

type MyBooksHandler struct {
	books      *service.BookService
	tasks      *service.TaskService
	dispatcher *dispatch.Dispatcher
}

func NewMyBooksHandler(books *service.BookService, tasks *service.TaskService, dispatcher *dispatch.Dispatcher) *MyBooksHandler {
	return &MyBooksHandler{books: books, tasks: tasks, dispatcher: dispatcher}
}

func loadMyBooksConfig() (config.MyBooksConfig, error) {
	cfg, err := config.LoadFromFile()
	if err != nil {
		return config.MyBooksConfig{}, fmt.Errorf("read config: %w", err)
	}
	return cfg.MyBooks, nil
}

func (h *MyBooksHandler) Test(c *gin.Context) {
	var body dto.MyBooksTestRequest
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	cfg := config.MyBooksConfig{BaseURL: body.BaseURL, Username: body.Username, Password: body.Password}
	if strings.TrimSpace(cfg.BaseURL) == "" {
		c.JSON(http.StatusOK, gin.H{"ok": false, "error": "base_url is required"})
		return
	}

	err := service.NewMyBooksService(cfg).Test(cfg)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"ok": false, "error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"ok": true})
}

func (h *MyBooksHandler) Search(c *gin.Context) {
	cfg, err := loadMyBooksConfig()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if strings.TrimSpace(cfg.BaseURL) == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "MyBooks is not configured"})
		return
	}

	name := strings.TrimSpace(c.Query("name"))
	if name == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "name is required"})
		return
	}
	start, size := parsePage(c.DefaultQuery("start", "0"), c.DefaultQuery("size", "20"))

	svc := service.NewMyBooksService(cfg)
	resp, err := svc.Search(name, start, size)
	if err != nil {
		log.Printf("[mybooks] search failed: %v", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, resp)
}

func (h *MyBooksHandler) Import(c *gin.Context) {
	var body dto.MyBooksImportRequest
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if body.MyBooksID <= 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "mybooks_id must be a positive integer"})
		return
	}

	cfg, err := loadMyBooksConfig()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if strings.TrimSpace(cfg.BaseURL) == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "MyBooks is not configured"})
		return
	}

	svc := service.NewMyBooksService(cfg)
	body.Format = strings.ToLower(body.Format)

	log.Printf("[mybooks] importing book=%d format=%s", body.MyBooksID, body.Format)

	reader, err := svc.DownloadFile(body.MyBooksID, body.Format)
	if err != nil {
		log.Printf("[mybooks] download failed: %v", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "download from MyBooks: " + err.Error()})
		return
	}
	defer reader.Close()

	tmpFile, err := os.CreateTemp("", "mybooks_import_*."+body.Format)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "create temp file: " + err.Error()})
		return
	}
	tmpPath := tmpFile.Name()
	defer os.Remove(tmpPath)

	if _, err := io.Copy(tmpFile, reader); err != nil {
		tmpFile.Close()
		c.JSON(http.StatusInternalServerError, gin.H{"error": "save temp file: " + err.Error()})
		return
	}
	tmpFile.Close()
	log.Printf("[mybooks] downloaded %d to %s", body.MyBooksID, tmpPath)

	book, task, existing, err := h.books.CreateBookWithMyBooksID(defaultUserID, body.Format, models.SourceOriginMyBooks, body.MyBooksID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if existing {
		if book.FilePath != "" {
			h.dispatcher.TryDispatch()
			c.JSON(http.StatusOK, dto.MyBooksImportResponse{BookID: book.ID, TaskID: task.ID})
			return
		}
		if err := h.books.SetStatus(book.ID, models.BookStatusPending); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
	}

	if _, err := h.books.SaveLocalFile(book.ID, tmpPath, body.Format); err != nil {
		if failErr := h.tasks.Fail(task.ID, err.Error()); failErr != nil {
			log.Printf("[mybooks] book %s: failed to mark ingest task failed: %v", book.ID, failErr)
		}
		if statusErr := h.books.SetStatus(book.ID, models.BookStatusFailed); statusErr != nil {
			log.Printf("[mybooks] book %s: failed to mark import failed: %v", book.ID, statusErr)
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "save book file: " + err.Error()})
		return
	}

	if coverURL := strings.TrimSpace(c.Query("cover_url")); coverURL != "" {
		if _, err := h.books.DownloadCover(book.ID, coverURL); err != nil {
			log.Printf("[mybooks] book %s: failed to download cover: %v", book.ID, err)
		}
	}

	currentTask, taskErr := h.tasks.GetTask(task.ID)
	if taskErr != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": taskErr.Error()})
		return
	}
	if currentTask.Status != models.TaskStatusPending && currentTask.Status != models.TaskStatusProcessing {
		if err := h.tasks.Retry(task.ID); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
	}

	h.dispatcher.TryDispatch()

	log.Printf("[mybooks] import ok book=%s task=%s mybooks_id=%d", book.ID, task.ID, body.MyBooksID)
	c.JSON(http.StatusOK, dto.MyBooksImportResponse{BookID: book.ID, TaskID: task.ID})
}

func parsePage(startStr, sizeStr string) (int, int) {
	start := 0
	if _, err := fmt.Sscanf(startStr, "%d", &start); err != nil || start < 0 {
		start = 0
	}
	size := 20
	if _, err := fmt.Sscanf(sizeStr, "%d", &size); err != nil || size < 1 {
		size = 20
	}
	if size > 50 {
		size = 50
	}
	return start, size
}
