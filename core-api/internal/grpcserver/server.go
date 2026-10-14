// Package grpcserver implements mynexuspb.CoreApiServiceServer — the gRPC
// counterpart of the old /internal/* HTTP handlers (internal_handler.go,
// removed) that Worker calls to report task progress/completion/failure and
// to run Postgres-only keyword search. See
// .claude/memory/mynexus_grpc_migration.md.
package grpcserver

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"strings"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/dispatch"
	"mynexus/core-api/internal/grpcapi/mynexuspb"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

type CoreAPIServer struct {
	mynexuspb.UnimplementedCoreApiServiceServer

	books      *service.BookService
	tasks      *service.TaskService
	worker     *coordinator.WorkerClient
	dispatcher *dispatch.Dispatcher
	cfg        config.Config
	llmUsage   *service.LLMUsageService
}

func New(cfg config.Config, books *service.BookService, tasks *service.TaskService, worker *coordinator.WorkerClient, dispatcher *dispatch.Dispatcher, llmUsage *service.LLMUsageService) *CoreAPIServer {
	return &CoreAPIServer{cfg: cfg, books: books, tasks: tasks, worker: worker, dispatcher: dispatcher, llmUsage: llmUsage}
}

// Serve blocks, listening on cfg.Server.GRPCPort — run it in a goroutine from main.go.
// Listen binds the gRPC port synchronously — call this from main() *before*
// anything that might call back into Worker (e.g. internal/dispatch.Dispatcher's
// startup recovery pass), which in turn calls back into this port to report
// progress. Split from Serve (below) specifically so main() can guarantee
// the port is actually bound before triggering any such call, rather than
// racing a background goroutine's net.Listen against it — that race was
// real and cost a requeued task its first dispatch attempt (Worker's
// TriggerIngest handler spawns its background thread and calls
// ReportProgress almost immediately; if this port isn't listening yet that
// call fails with UNAVAILABLE, and the task then sits dispatched-but-idle
// since Worker doesn't retry ReportProgress on its own — see
// worker/src/pipelines/ingestion.py's run(), which reports failure and
// stops rather than retrying the callback).
func (s *CoreAPIServer) Listen() (net.Listener, error) {
	lis, err := net.Listen("tcp", ":"+s.cfg.Server.GRPCPort)
	if err != nil {
		return nil, fmt.Errorf("listen on grpc port %s: %w", s.cfg.Server.GRPCPort, err)
	}
	return lis, nil
}

// Serve runs the accept loop against a listener obtained from Listen —
// blocking, meant to be run in its own goroutine from main().
func (s *CoreAPIServer) Serve(lis net.Listener) error {
	grpcServer := grpc.NewServer()
	mynexuspb.RegisterCoreApiServiceServer(grpcServer, s)
	return grpcServer.Serve(lis)
}

func (s *CoreAPIServer) ReportProgress(ctx context.Context, req *mynexuspb.ProgressRequest) (*mynexuspb.Ack, error) {
	task, err := s.tasks.GetTask(req.TaskId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "task not found: %v", err)
	}

	if err := s.tasks.UpdateProgress(req.TaskId, int(req.Progress), req.Stage, req.Message); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	// Only an ingest task in flight means the book itself is "processing" —
	// a summarize task running against an already-ready book shouldn't flip
	// its status backward (see ReportChapterSummary/ReportBookSummary below,
	// which is where a summarize task's own progress lives instead).
	if task.Type == models.TaskTypeIngest {
		if err := s.books.SetStatus(task.BookID, models.BookStatusProcessing); err != nil {
			return nil, status.Errorf(codes.Internal, "%v", err)
		}
	}
	return &mynexuspb.Ack{Ok: true}, nil
}

// ReportMetadata persists title/author/language as soon as Worker finishes
// parsing, independent of whether splitting/embedding later succeeds — see
// the rpc comment in mynexus.proto for why this exists as its own call
// instead of waiting for ReportComplete.
func (s *CoreAPIServer) ReportMetadata(ctx context.Context, req *mynexuspb.MetadataRequest) (*mynexuspb.Ack, error) {
	task, err := s.tasks.GetTask(req.TaskId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "task not found: %v", err)
	}

	book := req.Book
	if err := s.books.ApplyParsedMetadata(task.BookID, book.GetTitle(), book.GetAuthor(), book.GetLanguage()); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	return &mynexuspb.Ack{Ok: true}, nil
}

func (s *CoreAPIServer) ReportComplete(ctx context.Context, req *mynexuspb.CompleteRequest) (*mynexuspb.Ack, error) {
	task, err := s.tasks.GetTask(req.TaskId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "task not found: %v", err)
	}

	chapters := make([]service.ParsedChapter, 0, len(req.Chapters))
	for _, ch := range req.Chapters {
		chapters = append(chapters, service.ParsedChapter{
			ID: ch.Id, Title: ch.Title, Level: int(ch.Level), SortOrder: int(ch.SortOrder), Content: ch.Content,
		})
	}
	if err := s.books.SaveChapters(task.BookID, chapters); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}

	chunks := make([]service.ParsedChunk, 0, len(req.Chunks))
	for _, ch := range req.Chunks {
		chunks = append(chunks, service.ParsedChunk{
			ID: ch.Id, ChapterID: ch.ChapterId, Content: ch.Content,
			Position: int(ch.Position), TokenCount: int(ch.TokenCount), VectorID: ch.VectorId,
			StartOffset: int(ch.StartOffset), EndOffset: int(ch.EndOffset),
		})
	}
	if err := s.books.SaveChunks(task.BookID, chunks); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}

	book := req.Book
	if err := s.books.ApplyParsedMetadata(task.BookID, book.GetTitle(), book.GetAuthor(), book.GetLanguage()); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	if err := s.books.SetStatus(task.BookID, models.BookStatusReady); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	if err := s.tasks.Complete(req.TaskId); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	// This ingest task just freed a worker.max_concurrent_tasks slot —
	// immediately try handing the next queued one to Worker instead of
	// waiting for the next unrelated trigger/health-check tick to notice.
	s.dispatcher.TryDispatch()

	// Worker always tries to produce a cover (extracted from the EPUB, or
	// title-generated as a fallback — see worker/src/util/cover_generator.py)
	// regardless of whether one's already set, since it has no visibility
	// into Core API's database (see .claude/memory/mynexus_m2_decisions.md).
	// So the decision of whether to keep it lives here: only accept it if
	// the book doesn't already have a cover from an explicit cover_url given
	// at import time (BookHandler.Import) — that one wins by running first,
	// before this ingest even started. Best-effort either way; a cover is
	// never worth failing an otherwise-successful ingest over.
	if len(req.Cover) > 0 {
		if hasCover, err := s.books.HasCover(task.BookID); err == nil && !hasCover {
			_, _ = s.books.SaveCoverBytes(task.BookID, req.Cover, req.CoverContentType)
		}
	}

	// Auto-chain a summarize run onto every completed ingest (fresh import
	// or Rebuild — both go through TriggerIngest/ReportComplete) so chapter
	// + book summaries show up without the user having to separately click
	// "总结全书" in BookDetailView.vue afterwards. Best-effort: a chapterless
	// book (parser found nothing usable) or an unreachable Worker just skips
	// this silently rather than failing the ingest itself, which already
	// succeeded and shouldn't be reported as broken over this.
	if len(chapters) > 0 {
		s.autoSummarize(task.BookID)
	}

	return &mynexuspb.Ack{Ok: true}, nil
}

// autoSummarize fires the map-reduce summarization pipeline (see
// worker/src/pipelines/summary.py) for a book that just finished ingesting.
// Runs in "continue" mode (ForceRestart=false): chapters already carrying a
// summary in the database are skipped by worker, which is what makes a
// rebuild cheap — SaveChapters carries summaries over by title, so a rebuild
// triggered by an embedding-model or chunk-size change (content unchanged
// per chapter) only pays for the chapters that are genuinely missing one,
// plus the one whole-book reduce call. The manual "重新总结全书" button
// (book_handler.summarizeOne) stays on restart mode; that one is an explicit
// request to redo every chapter.
//
// Chapters are read back from the database rather than reusing ReportComplete's
// freshly parsed ones: ParsedChapter carries no Summary field, so passing
// those through would leave every chapter's summary empty in the request and
// defeat the skip above entirely.
func (s *CoreAPIServer) autoSummarize(bookID string) {
	book, err := s.books.GetBook(bookID)
	if err != nil {
		return
	}

	chapters, err := s.books.ListChapters(bookID)
	if err != nil || len(chapters) == 0 {
		return
	}

	task, err := s.tasks.CreateTask(bookID, book.UserID, models.TaskTypeSummarize)
	if err != nil {
		return
	}

	reqChapters := make([]coordinator.SummarizeChapter, 0, len(chapters))
	reused := 0
	for _, ch := range chapters {
		if strings.TrimSpace(ch.Summary) != "" {
			reused++
		}
		reqChapters = append(reqChapters, coordinator.SummarizeChapter{
			ID: ch.ID, Title: ch.Title, Level: ch.Level, Content: ch.Content, Summary: ch.Summary,
			Keywords: ch.Keywords,
		})
	}
	log.Printf("book %s: auto-summarize (continue) over %d chapter(s), %d already summarized", bookID, len(reqChapters), reused)
	if err := s.worker.TriggerSummarize(coordinator.SummarizeRequest{
		TaskID: task.ID, BookID: bookID, Chapters: reqChapters, ForceRestart: false, Language: book.Language,
	}); err != nil {
		_ = s.tasks.Fail(task.ID, err.Error())
	}
}

func (s *CoreAPIServer) ReportFail(ctx context.Context, req *mynexuspb.FailRequest) (*mynexuspb.Ack, error) {
	task, err := s.tasks.GetTask(req.TaskId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "task not found: %v", err)
	}

	// A user-cancelled run reports canceled=true (see worker summary.py's
	// CancelledError path) and gets the distinct terminal status so the UI
	// shows "已取消" instead of a red failure.
	if req.Canceled {
		err = s.tasks.Cancel(req.TaskId)
	} else {
		err = s.tasks.Fail(req.TaskId, req.ErrorMsg)
	}
	if err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	// See the matching guard in ReportProgress: a failed summarize run
	// shouldn't mark an already-ready book as failed.
	if task.Type == models.TaskTypeIngest {
		if err := s.books.SetStatus(task.BookID, models.BookStatusFailed); err != nil {
			return nil, status.Errorf(codes.Internal, "%v", err)
		}
		// Same reasoning as ReportComplete: a failed ingest task also frees
		// a worker.max_concurrent_tasks slot.
		s.dispatcher.TryDispatch()
	}
	return &mynexuspb.Ack{Ok: true}, nil
}

// ReportChapterSummary persists one chapter's summary immediately (the map
// step of a summarize task — see the rpc comment in mynexus.proto). Doesn't
// touch the book's status or the task's completion state.
func (s *CoreAPIServer) ReportChapterSummary(ctx context.Context, req *mynexuspb.ChapterSummaryRequest) (*mynexuspb.Ack, error) {
	if _, err := s.tasks.GetTask(req.TaskId); err != nil {
		return nil, status.Errorf(codes.NotFound, "task not found: %v", err)
	}

	keywords := make([]dto.KeywordResponse, 0, len(req.Keywords))
	for _, kw := range req.Keywords {
		keywords = append(keywords, dto.KeywordResponse{Term: kw.Term, Weight: kw.Weight})
	}
	keywordsJSON, err := json.Marshal(keywords)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal keywords: %v", err)
	}

	definitions := make([]dto.DefinitionResponse, 0, len(req.Definitions))
	for _, def := range req.Definitions {
		definitions = append(definitions, dto.DefinitionResponse{Name: def.Name, Content: def.Content})
	}
	definitionsJSON, err := json.Marshal(definitions)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal definitions: %v", err)
	}

	if err := s.books.UpdateChapterSummary(req.ChapterId, req.Summary, string(keywordsJSON), string(definitionsJSON)); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	return &mynexuspb.Ack{Ok: true}, nil
}

// ReportBookSummary persists the whole-book summary (the reduce step) and
// marks the summarize task completed.
func (s *CoreAPIServer) ReportBookSummary(ctx context.Context, req *mynexuspb.BookSummaryRequest) (*mynexuspb.Ack, error) {
	if _, err := s.tasks.GetTask(req.TaskId); err != nil {
		return nil, status.Errorf(codes.NotFound, "task not found: %v", err)
	}

	keywords := make([]dto.KeywordResponse, 0, len(req.Keywords))
	for _, kw := range req.Keywords {
		keywords = append(keywords, dto.KeywordResponse{Term: kw.Term, Weight: kw.Weight})
	}
	keywordsJSON, err := json.Marshal(keywords)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal keywords: %v", err)
	}

	if err := s.books.SetBookSummary(req.BookId, req.Summary, string(keywordsJSON)); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	if err := s.tasks.Complete(req.TaskId); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	return &mynexuspb.Ack{Ok: true}, nil
}

// ReportTokenUsage is the fire-and-forget accounting sink — it never fails
// the calling Worker's pipeline (summary / ingest / chat) because a
// book can still be perfectly useful even if one usage row couldn't be
// written. Errors are logged but we return Ok regardless so Worker-side
// retry logic (if any) doesn't kick in.
func (s *CoreAPIServer) ReportTokenUsage(ctx context.Context, req *mynexuspb.TokenUsageRequest) (*mynexuspb.Ack, error) {
	if err := s.llmUsage.Insert(
		req.GetTaskId(), req.GetBookId(), req.GetTaskType(),
		req.GetLlmProvider(), req.GetLlmModel(), req.GetCallSite(),
		int(req.GetPromptTokens()), int(req.GetCompletionTokens()), int(req.GetTotalTokens()),
	); err != nil {
		// Best-effort: log and swallow. Token accounting failing must
		// never abort an ingest or summarize task that was otherwise
		// producing real progress.
		fmt.Printf("WARN: ReportTokenUsage insert failed: %v\n", err)
	}
	return &mynexuspb.Ack{Ok: true}, nil
}

// KeywordSearch is Postgres-only (see .claude/memory/mynexus_keyword_search_gin.md);
// on SQLite it returns NOT_FOUND so Worker falls back to its in-process BM25 pass.
func (s *CoreAPIServer) KeywordSearch(ctx context.Context, req *mynexuspb.KeywordSearchRequest) (*mynexuspb.KeywordSearchResponse, error) {
	if s.cfg.Storage.Database != "postgres" {
		return nil, status.Error(codes.NotFound, "keyword search requires the postgres backend")
	}

	topK := int(req.TopK)
	if topK <= 0 {
		topK = 20
	}

	results, err := s.books.KeywordSearch(req.Query, req.BookIds, topK)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}

	items := make([]*mynexuspb.KeywordSearchResult, 0, len(results))
	for _, r := range results {
		items = append(items, &mynexuspb.KeywordSearchResult{ChunkId: r.ChunkID, BookId: r.BookID, Score: r.Score})
	}
	return &mynexuspb.KeywordSearchResponse{Results: items}, nil
}

// GetLibraryStats backs the chat assistant's "get_library_stats" tool (see
// .claude/memory/mynexus_chat_tool_calling.md) — read-only, no task/session
// context needed, unlike every other CoreApiService RPC above.
func (s *CoreAPIServer) GetLibraryStats(ctx context.Context, req *mynexuspb.LibraryStatsRequest) (*mynexuspb.LibraryStatsResponse, error) {
	counts, err := s.books.CountByStatus()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}

	total := 0
	byStatus := make([]*mynexuspb.BookStatusCount, 0, len(counts))
	for st, n := range counts {
		total += n
		byStatus = append(byStatus, &mynexuspb.BookStatusCount{Status: st, Count: int32(n)})
	}
	return &mynexuspb.LibraryStatsResponse{TotalBooks: int32(total), ByStatus: byStatus}, nil
}

// bookInfoMatchLimit caps how many books one GetBookInfo call can return —
// a vague/empty query shouldn't dump the whole library into a single tool
// result the LLM then has to wade through.
const bookInfoMatchLimit = 5

// GetChapterContent backs the chat assistant's "read_chapter" tool — see the
// rpc comment in mynexus.proto for why this exists as a separate lookup from
// GetBookInfo (sequential-reading questions need full cleaned chapter text,
// not metadata/summaries).
func (s *CoreAPIServer) GetChapterContent(ctx context.Context, req *mynexuspb.ChapterContentRequest) (*mynexuspb.ChapterContentResponse, error) {
	chapter, err := s.books.GetChapterByID(req.BookId, req.ChapterId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "chapter not found: %v", err)
	}
	return &mynexuspb.ChapterContentResponse{
		ChapterId: chapter.ID,
		Title:     chapter.Title,
		Content:   chapter.Content,
		SortOrder: int32(chapter.SortOrder),
	}, nil
}

// GetBookInfo backs the chat assistant's "get_book_info" tool (see
// .claude/memory/mynexus_chat_tool_calling.md) — returns book metadata plus
// the whole-book and per-chapter summaries already generated by
// worker/src/pipelines/summary.py, so the assistant can answer "这本书讲了
// 什么"/"作者是谁" style questions directly instead of falling back to
// chunk-level RAG retrieval for what's structurally a lookup.
func (s *CoreAPIServer) GetBookInfo(ctx context.Context, req *mynexuspb.BookInfoRequest) (*mynexuspb.BookInfoResponse, error) {
	books, _, err := s.books.ListBooks(1, bookInfoMatchLimit, "", req.Query)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}

	items := make([]*mynexuspb.BookInfo, 0, len(books))
	for _, b := range books {
		var tags []string
		_ = json.Unmarshal([]byte(b.Tags), &tags)

		chapters, err := s.books.ListChapters(b.ID)
		if err != nil {
			return nil, status.Errorf(codes.Internal, "%v", err)
		}
		chapterInfos := make([]*mynexuspb.ChapterInfo, 0, len(chapters))
		for _, c := range chapters {
			chapterInfos = append(chapterInfos, &mynexuspb.ChapterInfo{
				ChapterId: c.ID, Title: c.Title, Summary: c.Summary, SortOrder: int32(c.SortOrder),
			})
		}

		items = append(items, &mynexuspb.BookInfo{
			BookId: b.ID, Title: b.Title, Author: b.Author, Publisher: b.Publisher,
			Category: b.Category, Tags: tags, Summary: b.Summary, Chapters: chapterInfos,
		})
	}
	return &mynexuspb.BookInfoResponse{Books: items}, nil
}

// GetChapterSummaries serves Worker's post-ingest re-embed pass (see
// pipelines/ingestion.py): chapter summaries survive a rebuild in the
// database (SaveChapters carries them over by title), but their vector-store
// records don't survive Worker's own delete_by_book — this returns the
// non-empty ones plus the whole-book summary so Worker can re-embed them.
func (s *CoreAPIServer) GetChapterSummaries(ctx context.Context, req *mynexuspb.ChapterSummariesRequest) (*mynexuspb.ChapterSummariesResponse, error) {
	if req.BookId == "" {
		return nil, status.Errorf(codes.InvalidArgument, "book_id is required")
	}

	chapters, err := s.books.ListChapterSummaries(req.BookId)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	entries := make([]*mynexuspb.ChapterSummaryEntry, 0, len(chapters))
	for _, c := range chapters {
		entries = append(entries, &mynexuspb.ChapterSummaryEntry{ChapterId: c.ID, Summary: c.Summary})
	}

	bookSummary := ""
	if book, err := s.books.GetBook(req.BookId); err == nil {
		bookSummary = book.Summary
	}
	return &mynexuspb.ChapterSummariesResponse{Chapters: entries, BookSummary: bookSummary}, nil
}
