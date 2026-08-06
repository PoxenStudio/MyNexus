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
	"net"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/grpcapi/mynexuspb"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

type CoreAPIServer struct {
	mynexuspb.UnimplementedCoreApiServiceServer

	books *service.BookService
	tasks *service.TaskService
	cfg   config.Config
}

func New(cfg config.Config, books *service.BookService, tasks *service.TaskService) *CoreAPIServer {
	return &CoreAPIServer{cfg: cfg, books: books, tasks: tasks}
}

// Serve blocks, listening on cfg.Server.GRPCPort — run it in a goroutine from main.go.
func (s *CoreAPIServer) Serve() error {
	lis, err := net.Listen("tcp", ":"+s.cfg.Server.GRPCPort)
	if err != nil {
		return fmt.Errorf("listen on grpc port %s: %w", s.cfg.Server.GRPCPort, err)
	}

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

	return &mynexuspb.Ack{Ok: true}, nil
}

func (s *CoreAPIServer) ReportFail(ctx context.Context, req *mynexuspb.FailRequest) (*mynexuspb.Ack, error) {
	task, err := s.tasks.GetTask(req.TaskId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "task not found: %v", err)
	}

	if err := s.tasks.Fail(req.TaskId, req.ErrorMsg); err != nil {
		return nil, status.Errorf(codes.Internal, "%v", err)
	}
	// See the matching guard in ReportProgress: a failed summarize run
	// shouldn't mark an already-ready book as failed.
	if task.Type == models.TaskTypeIngest {
		if err := s.books.SetStatus(task.BookID, models.BookStatusFailed); err != nil {
			return nil, status.Errorf(codes.Internal, "%v", err)
		}
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
	if err := s.books.UpdateChapterSummary(req.ChapterId, req.Summary); err != nil {
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
