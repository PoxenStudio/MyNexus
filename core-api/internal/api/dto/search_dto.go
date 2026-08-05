package dto

type SearchRequest struct {
	Query          string   `json:"query" binding:"required"`
	BookIDs        []string `json:"book_ids"`
	TopK           int      `json:"top_k"`
	ScoreThreshold float64  `json:"score_threshold"`
	EnableRerank   bool     `json:"enable_rerank"`
}

type SearchResultResponse struct {
	ChunkID      string  `json:"chunk_id"`
	BookID       string  `json:"book_id"`
	BookTitle    string  `json:"book_title"`
	ChapterTitle string  `json:"chapter_title"`
	Content      string  `json:"content"`
	Score        float64 `json:"score"`
	TokenCount   int     `json:"token_count"`
	Position     int     `json:"position"`
}

type SearchResponse struct {
	Results      []SearchResultResponse `json:"results"`
	Total        int                    `json:"total"`
	SearchTimeMs int64                  `json:"search_time_ms"`
}

// KeywordSearchRequest/Response are for the Worker-facing internal endpoint
// (see internal_handler.go's KeywordSearch) — Postgres-only GIN-indexed
// full-text search, called by Worker's RetrievalPipeline in place of its
// in-process BM25 pass when storage.database == "postgres".
type KeywordSearchRequest struct {
	Query   string   `json:"query" binding:"required"`
	BookIDs []string `json:"book_ids"`
	TopK    int      `json:"top_k"`
}

type KeywordSearchResultItem struct {
	ChunkID string  `json:"chunk_id"`
	BookID  string  `json:"book_id"`
	Score   float64 `json:"score"`
}

type KeywordSearchResponse struct {
	Results []KeywordSearchResultItem `json:"results"`
}
