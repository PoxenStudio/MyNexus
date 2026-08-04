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
