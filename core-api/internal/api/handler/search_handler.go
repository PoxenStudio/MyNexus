package handler

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/service"
)

type SearchHandler struct {
	books  *service.BookService
	worker *coordinator.WorkerClient
}

func NewSearchHandler(books *service.BookService, worker *coordinator.WorkerClient) *SearchHandler {
	return &SearchHandler{books: books, worker: worker}
}

func (h *SearchHandler) Hybrid(c *gin.Context) {
	var req dto.SearchRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.TopK <= 0 {
		req.TopK = 10
	}

	start := time.Now()
	raw, err := h.worker.Search(coordinator.SearchRequest{
		Query: req.Query, BookIDs: req.BookIDs, TopK: req.TopK, ScoreThreshold: req.ScoreThreshold,
	})
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "search failed: " + err.Error()})
		return
	}

	results := make([]dto.SearchResultResponse, 0, len(raw))
	bookTitles := map[string]string{}
	for _, r := range raw {
		title, ok := bookTitles[r.BookID]
		if !ok {
			if b, err := h.books.GetBook(r.BookID); err == nil {
				title = b.Title
			}
			bookTitles[r.BookID] = title
		}
		chapterTitle, _ := h.books.ChapterTitle(r.ChapterID)

		results = append(results, dto.SearchResultResponse{
			ChunkID: r.ID, BookID: r.BookID, BookTitle: title, ChapterTitle: chapterTitle,
			Content: r.Content, Score: r.Score, TokenCount: r.TokenCount, Position: r.Position,
		})
	}

	c.JSON(http.StatusOK, dto.SearchResponse{
		Results: results, Total: len(results), SearchTimeMs: time.Since(start).Milliseconds(),
	})
}
