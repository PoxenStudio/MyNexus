package handler

import (
	"encoding/json"
	"errors"
	"net/http"
	"path/filepath"
	"strings"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/service"
)

const maxImportRequestSize = service.MaxTransferUploadSize + (1 << 20)

type TransferHandler struct {
	transfers *service.TransferService
}

type createExportRequest struct {
	BookID string `json:"book_id" binding:"required"`
}

type transferJobResponse struct {
	ID             string          `json:"id"`
	BookID         string          `json:"book_id"`
	Type           string          `json:"type"`
	Status         string          `json:"status"`
	Stage          string          `json:"stage"`
	Progress       int             `json:"progress"`
	ErrorMsg       string          `json:"error_msg"`
	TargetFileName string          `json:"target_file_name,omitempty"`
	SourceTitle    string          `json:"source_title,omitempty"`
	Preview        json.RawMessage `json:"preview,omitempty"`
	CreatedAt      string          `json:"created_at"`
	UpdatedAt      string          `json:"updated_at"`
}

func NewTransferHandler(transfers *service.TransferService) *TransferHandler {
	return &TransferHandler{transfers: transfers}
}

func newTransferJobResponse(job *service.TransferJob) transferJobResponse {
	response := transferJobResponse{
		ID: job.ID, BookID: job.BookID, Type: job.Type, Status: job.Status, Stage: job.Stage,
		Progress: job.Progress, ErrorMsg: job.ErrorMsg, TargetFileName: job.TargetFileName,
		SourceTitle: job.SourceTitle, CreatedAt: job.CreatedAt, UpdatedAt: job.UpdatedAt,
	}
	if job.Preview != "" && json.Valid([]byte(job.Preview)) {
		response.Preview = json.RawMessage(job.Preview)
	}
	return response
}

func (h *TransferHandler) Import(c *gin.Context) {
	c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, maxImportRequestSize)
	if err := c.Request.ParseMultipartForm(32 << 20); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid or oversized upload"})
		return
	}
	if c.Request.MultipartForm != nil {
		defer c.Request.MultipartForm.RemoveAll()
	}
	file, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "file is required"})
		return
	}
	if strings.ToLower(filepath.Ext(file.Filename)) != ".zip" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "only ZIP archives are supported"})
		return
	}
	bookID := c.Param("id")
	job, err := h.transfers.CreateImport(bookID, file)
	if err != nil {
		status := http.StatusInternalServerError
		switch {
		case errors.Is(err, service.ErrBookNotFound):
			status = http.StatusNotFound
		case errors.Is(err, service.ErrTransferInProgress):
			status = http.StatusConflict
		case strings.Contains(err.Error(), "file must be between"), strings.Contains(err.Error(), "exceeds"):
			status = http.StatusBadRequest
		}
		c.JSON(status, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusAccepted, newTransferJobResponse(job))
}

func (h *TransferHandler) ActiveImport(c *gin.Context) {
	job, err := h.transfers.ActiveImport(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if job == nil {
		c.Status(http.StatusNoContent)
		return
	}
	c.JSON(http.StatusOK, newTransferJobResponse(job))
}

func (h *TransferHandler) Get(c *gin.Context) {
	job, err := h.transfers.Get(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "transfer task not found"})
		return
	}
	c.JSON(http.StatusOK, newTransferJobResponse(job))
}

func (h *TransferHandler) ConfirmImport(c *gin.Context) {
	job, err := h.transfers.ConfirmImport(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusConflict, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusAccepted, newTransferJobResponse(job))
}

func (h *TransferHandler) CancelImport(c *gin.Context) {
	job, err := h.transfers.CancelImport(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusConflict, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, newTransferJobResponse(job))
}

func (h *TransferHandler) CreateExport(c *gin.Context) {
	var request createExportRequest
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "book_id is required"})
		return
	}
	job, err := h.transfers.CreateExport(request.BookID)
	if err != nil {
		status := http.StatusInternalServerError
		if errors.Is(err, service.ErrTransferInProgress) {
			status = http.StatusConflict
		} else if errors.Is(err, service.ErrBookNotFound) {
			status = http.StatusNotFound
		} else if strings.Contains(err.Error(), "no exportable derived data") {
			status = http.StatusConflict
		}
		c.JSON(status, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusAccepted, newTransferJobResponse(job))
}

func (h *TransferHandler) GetExport(c *gin.Context) {
	job, err := h.transfers.Get(c.Param("id"))
	if err != nil || job.Type != service.TransferTypeExport {
		c.JSON(http.StatusNotFound, gin.H{"error": "export task not found"})
		return
	}
	c.JSON(http.StatusOK, newTransferJobResponse(job))
}
