package coordinator

import (
	"context"
	"fmt"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"mynexus/core-api/internal/grpcapi/mynexuspb"
)

// WorkerClient wraps a single persistent gRPC connection to Worker (see
// .claude/memory/mynexus_grpc_migration.md for why this replaced the earlier
// one-shot HTTP+JSON calls: one long-lived HTTP/2 connection instead of a new
// TCP/TLS handshake per request, binary protobuf instead of JSON marshaling,
// and native support for the Chat streaming case). Call-site-facing method
// signatures below are unchanged from the HTTP-era client on purpose, so
// book_handler.go/search_handler.go/chat_handler.go didn't need to change.
type WorkerClient struct {
	conn   *grpc.ClientConn
	client mynexuspb.WorkerServiceClient
}

// NewWorkerClient dials target (a bare "host:port" authority, e.g.
// "worker:8001" in Docker or "localhost:8001" locally — no "http://" scheme).
// The connection is lazy/non-blocking: grpc-go connects on first RPC and
// transparently reconnects on failure, so a Worker that isn't up yet at Core
// API startup isn't a hard error here.
func NewWorkerClient(target string) *WorkerClient {
	conn, err := grpc.NewClient(target, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		// grpc.NewClient only fails on malformed target strings, not connectivity —
		// a bad config value is a startup-time bug worth crashing loudly for.
		panic(fmt.Sprintf("invalid worker grpc target %q: %v", target, err))
	}
	return &WorkerClient{conn: conn, client: mynexuspb.NewWorkerServiceClient(conn)}
}

func (c *WorkerClient) Close() error {
	return c.conn.Close()
}

type IngestRequest struct {
	TaskID           string
	BookID           string
	FilePath         string
	OriginalFilename string
}

// TriggerIngest asks Worker to start parsing file_path in the background.
// Worker replies immediately and reports progress/completion asynchronously
// via its own gRPC calls back to Core API's CoreApiService (see grpcserver package).
func (c *WorkerClient) TriggerIngest(req IngestRequest) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	_, err := c.client.TriggerIngest(ctx, &mynexuspb.IngestRequest{
		TaskId: req.TaskID, BookId: req.BookID, FilePath: req.FilePath, OriginalFilename: req.OriginalFilename,
	})
	if err != nil {
		return fmt.Errorf("call worker TriggerIngest: %w", err)
	}
	return nil
}

type SearchRequest struct {
	Query          string
	BookIDs        []string
	TopK           int
	ScoreThreshold float64
}

type SearchResultRaw struct {
	ID         string
	BookID     string
	ChapterID  string
	Content    string
	Position   int
	TokenCount int
	Score      float64
}

// Search executes hybrid retrieval synchronously and returns raw results
// (chunk/chapter/book ids only — Core API enriches with titles afterward).
func (c *WorkerClient) Search(req SearchRequest) ([]SearchResultRaw, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	resp, err := c.client.Search(ctx, &mynexuspb.SearchRequest{
		Query: req.Query, BookIds: req.BookIDs, TopK: int32(req.TopK), ScoreThreshold: req.ScoreThreshold,
	})
	if err != nil {
		return nil, fmt.Errorf("call worker Search: %w", err)
	}

	results := make([]SearchResultRaw, 0, len(resp.Results))
	for _, r := range resp.Results {
		results = append(results, SearchResultRaw{
			ID: r.ChunkId, BookID: r.BookId, ChapterID: r.ChapterId, Content: r.Content,
			Position: int(r.Position), TokenCount: int(r.TokenCount), Score: r.Score,
		})
	}
	return results, nil
}

type ChatMessage struct {
	Role    string
	Content string
}

type ChatRequest struct {
	Messages []ChatMessage
	BookIDs  []string
	TopK     int
}

// ChatEvent is one item from a Chat stream: exactly one of Delta (an answer
// text fragment) or Citations (the final message) is set.
type ChatEvent struct {
	Delta     string
	Citations []Citation
}

type Citation struct {
	ChunkID   string
	ChapterID string
	BookID    string
	Score     float64
	Content   string
}

// ChatStream lets the caller pull streamed chat events one at a time —
// chat_handler.go relays each as an SSE frame to the browser, same shape as
// before the gRPC migration, just sourced from a gRPC stream instead of
// scanning an HTTP response body line by line.
type ChatStream struct {
	stream grpc.ServerStreamingClient[mynexuspb.ChatChunk]
}

// Recv returns the next event, or io.EOF when the stream has ended normally.
func (s *ChatStream) Recv() (ChatEvent, error) {
	chunk, err := s.stream.Recv()
	if err != nil {
		return ChatEvent{}, err // includes io.EOF
	}

	switch payload := chunk.Payload.(type) {
	case *mynexuspb.ChatChunk_Delta:
		return ChatEvent{Delta: payload.Delta}, nil
	case *mynexuspb.ChatChunk_Citations:
		citations := make([]Citation, 0, len(payload.Citations.Items))
		for _, c := range payload.Citations.Items {
			citations = append(citations, Citation{
				ChunkID: c.ChunkId, ChapterID: c.ChapterId, BookID: c.BookId, Score: c.Score, Content: c.Content,
			})
		}
		return ChatEvent{Citations: citations}, nil
	default:
		return ChatEvent{}, nil
	}
}

// Chat starts a streaming RAG answer. The caller must drain the stream (Recv
// until io.EOF) to release the underlying gRPC stream.
func (c *WorkerClient) Chat(req ChatRequest) (*ChatStream, error) {
	messages := make([]*mynexuspb.ChatMessage, 0, len(req.Messages))
	for _, m := range req.Messages {
		messages = append(messages, &mynexuspb.ChatMessage{Role: m.Role, Content: m.Content})
	}

	// No context timeout here — chat responses stream for as long as the LLM
	// takes, which a short control-plane deadline would cut off (mirrors the
	// old streamClient-with-no-Timeout used for the HTTP-era SSE relay).
	stream, err := c.client.Chat(context.Background(), &mynexuspb.ChatRequest{
		Messages: messages, BookIds: req.BookIDs, TopK: int32(req.TopK),
	})
	if err != nil {
		return nil, fmt.Errorf("call worker Chat: %w", err)
	}
	return &ChatStream{stream: stream}, nil
}
