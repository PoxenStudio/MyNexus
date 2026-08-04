package coordinator

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type WorkerClient struct {
	baseURL string
	client  *http.Client
	// streamClient has no timeout: chat responses stream for as long as the
	// LLM takes, which a short control-plane timeout would cut off.
	streamClient *http.Client
}

func NewWorkerClient(baseURL string) *WorkerClient {
	return &WorkerClient{
		baseURL:      strings.TrimRight(baseURL, "/"),
		client:       &http.Client{Timeout: 10 * time.Second},
		streamClient: &http.Client{},
	}
}

type IngestRequest struct {
	TaskID           string `json:"task_id"`
	BookID           string `json:"book_id"`
	FilePath         string `json:"file_path"`
	OriginalFilename string `json:"original_filename"`
	CallbackBaseURL  string `json:"callback_base_url"`
}

// TriggerIngest asks Worker to start parsing file_path in the background.
// Worker replies 202 immediately and reports progress/completion asynchronously
// via HTTP callbacks to CallbackBaseURL (see internal_handler.go).
func (c *WorkerClient) TriggerIngest(req IngestRequest) error {
	body, err := json.Marshal(req)
	if err != nil {
		return fmt.Errorf("marshal ingest request: %w", err)
	}

	resp, err := c.client.Post(c.baseURL+"/internal/ingest", "application/json", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("call worker /internal/ingest: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return fmt.Errorf("worker /internal/ingest returned status %d", resp.StatusCode)
	}
	return nil
}

type SearchRequest struct {
	Query          string   `json:"query"`
	BookIDs        []string `json:"book_ids,omitempty"`
	TopK           int      `json:"top_k"`
	ScoreThreshold float64  `json:"score_threshold"`
}

type SearchResultRaw struct {
	ID         string  `json:"id"`
	BookID     string  `json:"book_id"`
	ChapterID  string  `json:"chapter_id"`
	Content    string  `json:"content"`
	Position   int     `json:"position"`
	TokenCount int     `json:"token_count"`
	Score      float64 `json:"score"`
}

type searchResponse struct {
	Results []SearchResultRaw `json:"results"`
}

// Search executes hybrid retrieval synchronously and returns raw results
// (chunk/chapter/book ids only — Core API enriches with titles afterward).
func (c *WorkerClient) Search(req SearchRequest) ([]SearchResultRaw, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal search request: %w", err)
	}

	resp, err := c.client.Post(c.baseURL+"/internal/search", "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("call worker /internal/search: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("worker /internal/search returned status %d", resp.StatusCode)
	}

	var out searchResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, fmt.Errorf("decode search response: %w", err)
	}
	return out.Results, nil
}

type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatRequest struct {
	Messages []ChatMessage `json:"messages"`
	BookIDs  []string      `json:"book_ids,omitempty"`
	TopK     int           `json:"top_k"`
}

// Chat starts a streaming RAG answer and returns the raw SSE response body
// for the caller to relay line-by-line to its own client (see chat_handler.go).
// The caller owns closing the returned body.
func (c *WorkerClient) Chat(req ChatRequest) (io.ReadCloser, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal chat request: %w", err)
	}

	httpReq, err := http.NewRequest(http.MethodPost, c.baseURL+"/internal/chat", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("build chat request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.streamClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("call worker /internal/chat: %w", err)
	}
	if resp.StatusCode >= 300 {
		resp.Body.Close()
		return nil, fmt.Errorf("worker /internal/chat returned status %d", resp.StatusCode)
	}
	return resp.Body, nil
}
