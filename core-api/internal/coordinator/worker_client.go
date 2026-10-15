package coordinator

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/status"

	"mynexus/core-api/internal/grpcapi/mynexuspb"
)

// wrapWorkerError turns a low-level gRPC transport error into a short,
// user-facing message. The original error (code, connection-refused detail,
// etc.) is intentionally dropped here — it's already been logged by the
// caller; the front-end should only see "Worker 服务不可用" not a 150-char
// "rpc error: code = Unavailable desc = transport: Error while dialing:
// dial tcp 127.0.0.1:8001: connect: connection refused".
func wrapWorkerError(err error) error {
	if err == nil {
		return nil
	}
	if s, ok := status.FromError(err); ok {
		switch s.Code() {
		case codes.Unavailable, codes.ResourceExhausted:
			return fmt.Errorf("Worker 服务不可用，请确认 worker 进程已启动")
		case codes.DeadlineExceeded:
			return fmt.Errorf("Worker 响应超时，请稍后重试")
		}
	}
	msg := err.Error()
	if strings.Contains(msg, "connection refused") || strings.Contains(msg, "dial tcp") || strings.Contains(msg, "no such host") {
		return fmt.Errorf("Worker 服务不可用，请确认 worker 进程已启动")
	}
	return err
}

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
//
// Keepalive pings are explicit (not the grpc-go default of "none") so a dead
// Worker — process crashed, container killed, network cut — is detected via
// ConnState() within roughly PingTime+PingTimeout even with no task in
// flight, instead of only surfacing on the next RPC attempt. Used by
// main.go's watchWorkerHealth to fail any task stuck pending/processing
// against an unreachable Worker (see task_service.go's ReconcileOrphaned).
func NewWorkerClient(target string) *WorkerClient {
	conn, err := grpc.NewClient(
		target,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithKeepaliveParams(keepalive.ClientParameters{
			Time:                10 * time.Second,
			Timeout:             5 * time.Second,
			PermitWithoutStream: true,
		}),
	)
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

// ConnState reports the gRPC channel's current connectivity state — see
// watchWorkerHealth (main.go), which polls this to detect an unreachable
// Worker.
func (c *WorkerClient) ConnState() connectivity.State {
	return c.conn.GetState()
}

// Connect nudges an idle channel into actively attempting a connection.
// grpc.NewClient is lazy by default (it only connects when the first RPC is
// made), so without this a channel that's never been used for a real call
// would sit at Idle indefinitely and ConnState() would never reflect whether
// Worker is actually reachable.
func (c *WorkerClient) Connect() {
	c.conn.Connect()
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
	return wrapWorkerError(err)
}

type SummarizeChapter struct {
	ID         string
	Title      string
	Level      int
	Content    string
	Summary    string
	Keywords   string
	References string
}

type SummarizeRequest struct {
	TaskID   string
	BookID   string
	Chapters []SummarizeChapter
	// ForceRestart: when false, chapters that already carry a Summary are
	// left alone by Worker and only the missing ones are (re)generated
	// ("continue"). When true, every chapter is regenerated regardless of
	// any existing summary ("restart").
	ForceRestart bool
	// Language is the book's language code (books.language — see
	// worker/src/util/lang_detect.py). Selects the prompt language and
	// keyword-extraction path in worker/src/pipelines/summary.py; empty is
	// treated the same as Chinese.
	Language string
}

// TriggerSummarize asks Worker to start a map-reduce summarization run in
// the background. Chapters are sent in the request (not fetched by Worker)
// since Worker never touches Core API's database directly — see the rpc
// comment in mynexus.proto.
func (c *WorkerClient) TriggerSummarize(req SummarizeRequest) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	chapters := make([]*mynexuspb.Chapter, 0, len(req.Chapters))
	for _, ch := range req.Chapters {
		var kwList []struct {
			Term   string  `json:"term"`
			Weight float64 `json:"weight"`
		}
		if ch.Keywords != "" {
			_ = json.Unmarshal([]byte(ch.Keywords), &kwList)
		}
		pbKw := make([]*mynexuspb.Keyword, 0, len(kwList))
		for _, kw := range kwList {
			pbKw = append(pbKw, &mynexuspb.Keyword{Term: kw.Term, Weight: kw.Weight})
		}
		var refList []string
		if ch.References != "" {
			_ = json.Unmarshal([]byte(ch.References), &refList)
		}
		chapters = append(chapters, &mynexuspb.Chapter{
			Id: ch.ID, Title: ch.Title, Level: int32(ch.Level), Content: ch.Content, Summary: ch.Summary,
			Keywords:   pbKw,
			References: refList,
		})
	}

	_, err := c.client.TriggerSummarize(ctx, &mynexuspb.SummarizeRequest{
		TaskId: req.TaskID, BookId: req.BookID, Chapters: chapters, ForceRestart: req.ForceRestart,
		Language: req.Language,
	})
	return wrapWorkerError(err)
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
		return nil, wrapWorkerError(err)
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
	ChunkID     string
	ChapterID   string
	BookID      string
	Score       float64
	Content     string
	StartOffset int
	EndOffset   int
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
				StartOffset: int(c.StartOffset), EndOffset: int(c.EndOffset),
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
		return nil, wrapWorkerError(err)
	}
	return &ChatStream{stream: stream}, nil
}

// DeleteBook purges bookID's vector-store records on Worker. Called on book
// delete and before rebuild's re-ingest so ChromaDB/SimpleVectorStore never
// accumulates orphaned embeddings for a book_id no longer in Core API's own
// books/chunks tables (see .claude/memory/mynexus_orphaned_vectors.md) —
// those otherwise still surface as unresolvable citations in chat.
// ReembedBookSummary asks Worker to re-embed just the whole-book summary
// chunk (stable id "{book_id}:summary" — see
// worker/src/pipelines/summary.py's _index_summary) after a manual edit via
// BookHandler.UpdateSummary. Synchronous but cheap (one embedding call);
// best-effort — callers should log-and-continue on error rather than fail
// the edit itself, since the summary text is already persisted by then.
func (c *WorkerClient) ReembedBookSummary(bookID, summary string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	_, err := c.client.ReembedBookSummary(ctx, &mynexuspb.ReembedBookSummaryRequest{BookId: bookID, Summary: summary})
	return wrapWorkerError(err)
}

func (c *WorkerClient) DeleteBook(bookID string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	_, err := c.client.DeleteBook(ctx, &mynexuspb.DeleteBookRequest{BookId: bookID})
	return wrapWorkerError(err)
}

type VectorRecord struct {
	ID          string
	BookID      string
	ChapterID   string
	Content     string
	Position    int
	TokenCount  int
	StartOffset int
	EndOffset   int
	Embedding   []float32
}

func (c *WorkerClient) ExportBookVectors(bookID string, consume func(VectorRecord) error) error {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()

	stream, err := c.client.ExportBookVectors(ctx, &mynexuspb.VectorBookRequest{BookId: bookID})
	if err != nil {
		return wrapWorkerError(err)
	}
	for {
		record, err := stream.Recv()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return wrapWorkerError(err)
		}
		if err := consume(VectorRecord{
			ID: record.Id, BookID: record.BookId, ChapterID: record.ChapterId, Content: record.Content,
			Position: int(record.Position), TokenCount: int(record.TokenCount),
			StartOffset: int(record.StartOffset), EndOffset: int(record.EndOffset),
			Embedding: record.Embedding,
		}); err != nil {
			return err
		}
	}
}

func (c *WorkerClient) ImportBookVectors(
	ctx context.Context,
	produce func(func(VectorRecord) error) error,
) error {
	stream, err := c.client.ImportBookVectors(ctx)
	if err != nil {
		return wrapWorkerError(err)
	}
	err = produce(func(record VectorRecord) error {
		return stream.Send(&mynexuspb.VectorRecord{
			Id: record.ID, BookId: record.BookID, ChapterId: record.ChapterID, Content: record.Content,
			Position: int32(record.Position), TokenCount: int32(record.TokenCount),
			StartOffset: int32(record.StartOffset), EndOffset: int32(record.EndOffset),
			Embedding: record.Embedding,
		})
	})
	if err != nil {
		_ = stream.CloseSend()
		return err
	}
	_, err = stream.CloseAndRecv()
	return wrapWorkerError(err)
}

func (c *WorkerClient) CommitBookVectorImport(bookID, stagingBookID, backupBookID string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	_, err := c.client.CommitBookVectorImport(ctx, &mynexuspb.CommitBookVectorImportRequest{
		BookId: bookID, StagingBookId: stagingBookID, BackupBookId: backupBookID,
	})
	return wrapWorkerError(err)
}

func (c *WorkerClient) RollbackBookVectorImport(bookID, stagingBookID, backupBookID string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	_, err := c.client.RollbackBookVectorImport(ctx, &mynexuspb.RollbackBookVectorImportRequest{
		BookId: bookID, StagingBookId: stagingBookID, BackupBookId: backupBookID,
	})
	return wrapWorkerError(err)
}

func (c *WorkerClient) FinalizeBookVectorImport(stagingBookID, backupBookID string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	_, err := c.client.FinalizeBookVectorImport(ctx, &mynexuspb.FinalizeBookVectorImportRequest{
		StagingBookId: stagingBookID, BackupBookId: backupBookID,
	})
	return wrapWorkerError(err)
}

// CancelTask asks Worker to interrupt a running background task (see the rpc
// comment in mynexus.proto). found=false means Worker has no active run with
// that id (e.g. it restarted and lost its in-memory state) — the caller then
// marks the task canceled directly instead of waiting for a report.
func (c *WorkerClient) CancelTask(taskID string) (found bool, err error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	ack, err := c.client.CancelTask(ctx, &mynexuspb.CancelTaskRequest{TaskId: taskID})
	if err != nil {
		return false, wrapWorkerError(err)
	}
	return ack.Ok, nil
}

// Shutdown asks Worker to exit shortly after acking, so it restarts and
// picks up a just-saved config.yaml (see system_settings.go). Best-effort:
// callers should ignore the error (Worker being unreachable already means
// there's no running process to restart).
func (c *WorkerClient) Shutdown() error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := c.client.Shutdown(ctx, &mynexuspb.ShutdownRequest{})
	return wrapWorkerError(err)
}
