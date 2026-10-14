package service

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/google/uuid"
)

// LLMUsageService persists one LLM call's token consumption per row and
// aggregates for the book-detail token card and the dashboard — see
// core-api/internal/storage/*/migrations/*_token_usage.sql.
type LLMUsageService struct {
	db *sql.DB
}

func NewLLMUsageService(db *sql.DB) *LLMUsageService {
	return &LLMUsageService{db: db}
}

// Insert writes one usage row — called by ReportTokenUsage. Fire-and-forget
// from the Worker side; any error here is returned to the handler which then
// swallows it (see grpcserver.server.go's ReportTokenUsage) so a failed
// accounting row never aborts the actual LLM-driven work.
func (s *LLMUsageService) Insert(
	taskID, bookID, taskType, llmProvider, llmModel, callSite string,
	promptTokens, completionTokens, totalTokens int,
) error {
	_, err := s.db.Exec(
		`INSERT INTO token_usage
		 (id, task_id, book_id, task_type, llm_provider, llm_model, call_site, prompt_tokens, completion_tokens, total_tokens, created_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		uuid.NewString(), taskID, bookID, taskType, llmProvider, llmModel, callSite,
		promptTokens, completionTokens, totalTokens, time.Now().UTC().Format(time.RFC3339),
	)
	if err != nil {
		return fmt.Errorf("insert token_usage: %w", err)
	}
	return nil
}

// SumByBook returns {total_tokens, prompt_tokens, completion_tokens, calls} aggregated
// across a book's rows — backs the book-detail token card.
func (s *LLMUsageService) SumByBook(bookID string) (total, prompt, completion, calls int, err error) {
	row := s.db.QueryRow(
		`SELECT COALESCE(SUM(total_tokens),0), COALESCE(SUM(prompt_tokens),0),
		        COALESCE(SUM(completion_tokens),0), COUNT(1)
		 FROM token_usage WHERE book_id = ?`, bookID)
	err = row.Scan(&total, &prompt, &completion, &calls)
	if err != nil {
		return 0, 0, 0, 0, fmt.Errorf("sum token_usage by book: %w", err)
	}
	return
}

// CallSiteBreakdown returns per-call_site totals for a book — lets the
// book-detail card break down where the tokens went (chapter_analyze vs
// book_reduce vs ...). Rows come back ordered by total_tokens desc so the
// "top consumers" are upfront without an extra sort on the caller side.
type CallSiteRow struct {
	CallSite         string
	LLMProvider      string
	LLMModel         string
	Calls            int
	PromptTokens     int
	CompletionTokens int
	TotalTokens      int
}

func (s *LLMUsageService) CallSiteBreakdown(bookID string, limit int) ([]CallSiteRow, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.db.Query(
		`SELECT call_site, llm_provider, llm_model, COUNT(1),
		        COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0),
		        COALESCE(SUM(total_tokens),0)
		 FROM token_usage WHERE book_id = ?
		 GROUP BY call_site, llm_provider, llm_model
		 ORDER BY total_tokens DESC LIMIT ?`, bookID, limit)
	if err != nil {
		return nil, fmt.Errorf("callsite breakdown: %w", err)
	}
	defer rows.Close()
	var out []CallSiteRow
	for rows.Next() {
		var r CallSiteRow
		if err := rows.Scan(&r.CallSite, &r.LLMProvider, &r.LLMModel, &r.Calls,
			&r.PromptTokens, &r.CompletionTokens, &r.TotalTokens); err != nil {
			return nil, fmt.Errorf("scan callsite breakdown: %w", err)
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// DailyByProvider groups rows into one bucket per (date, llm_provider) and
// returns them most-recent-first — backs the dashboard折线图 (date x provider
// 双维度) and the饼图 (latest-day provider 占比). rangeDays caps the window;
// pass 0 for no cap.
type DailyProviderRow struct {
	Date             string
	LLMProvider      string
	PromptTokens     int
	CompletionTokens int
	TotalTokens      int
}

func (s *LLMUsageService) DailyByProvider(rangeDays int) ([]DailyProviderRow, error) {
	q := `SELECT DATE(created_at) as day, llm_provider,
		      COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0),
		      COALESCE(SUM(total_tokens),0)
		   FROM token_usage`
	args := []any{}
	if rangeDays > 0 {
		q += ` WHERE created_at >= DATE('now', ?)`
		args = append(args, fmt.Sprintf("-%d days", rangeDays-1))
	}
	q += ` GROUP BY DATE(created_at), llm_provider ORDER BY day DESC, llm_provider ASC`
	rows, err := s.db.Query(q, args...)
	if err != nil {
		return nil, fmt.Errorf("daily token_usage: %w", err)
	}
	defer rows.Close()

	var out []DailyProviderRow
	for rows.Next() {
		var r DailyProviderRow
		if err := rows.Scan(&r.Date, &r.LLMProvider, &r.PromptTokens, &r.CompletionTokens, &r.TotalTokens); err != nil {
			return nil, fmt.Errorf("scan daily token_usage: %w", err)
		}
		out = append(out, r)
	}
	return out, rows.Err()
}
