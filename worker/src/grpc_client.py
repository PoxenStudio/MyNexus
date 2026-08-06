"""Worker's gRPC client to Core API's CoreApiService — replaces the old
urllib-based HTTP callbacks (task progress/complete/fail) and the keyword
search HTTP call added for the Postgres GIN work. See
.claude/memory/mynexus_grpc_migration.md and mynexus_keyword_search_gin.md.
"""

import grpc

import mynexus_pb2
import mynexus_pb2_grpc
from config import WorkerConfig


class CoreApiClient:
    def __init__(self, config: WorkerConfig) -> None:
        # A single persistent channel, reused across every RPC — this is the
        # main point of the gRPC migration: no new TCP/TLS handshake per call.
        self._channel = grpc.insecure_channel(config.core_api_base_url)
        self._stub = mynexus_pb2_grpc.CoreApiServiceStub(self._channel)

    def report_progress(self, task_id: str, progress: int, stage: str, message: str = "") -> None:
        self._stub.ReportProgress(
            mynexus_pb2.ProgressRequest(task_id=task_id, progress=progress, stage=stage, message=message)
        )

    def report_metadata(self, task_id: str, document) -> None:
        """Persists title/author/language as soon as parsing succeeds, before
        the (slower, more failure-prone) splitting/embedding stages run — see
        ingestion.py's run()."""
        book = mynexus_pb2.BookMeta(title=document.title, author=document.author, language=document.language)
        self._stub.ReportMetadata(mynexus_pb2.MetadataRequest(task_id=task_id, book=book))

    def report_complete(self, task_id: str, document, chunks: list) -> None:
        book = mynexus_pb2.BookMeta(title=document.title, author=document.author, language=document.language)
        chapters = [
            mynexus_pb2.Chapter(id=c.id, title=c.title, level=c.level, sort_order=c.order, content=c.content)
            for c in document.chapters
        ]
        chunk_msgs = [
            mynexus_pb2.Chunk(
                id=c.id,
                chapter_id=c.chapter_id,
                content=c.content,
                position=c.position,
                token_count=c.token_count,
                vector_id=c.id,  # local vector store keys by chunk id
            )
            for c in chunks
        ]
        self._stub.ReportComplete(
            mynexus_pb2.CompleteRequest(task_id=task_id, book=book, chapters=chapters, chunks=chunk_msgs)
        )

    def report_fail(self, task_id: str, error_msg: str) -> None:
        self._stub.ReportFail(mynexus_pb2.FailRequest(task_id=task_id, error_msg=error_msg))

    def report_chapter_summary(self, task_id: str, chapter_id: str, summary: str) -> None:
        """Map step of summarization (see pipelines/summary.py): persists one
        chapter's summary immediately, so progress survives a mid-run crash."""
        self._stub.ReportChapterSummary(
            mynexus_pb2.ChapterSummaryRequest(task_id=task_id, chapter_id=chapter_id, summary=summary)
        )

    def report_book_summary(
        self, task_id: str, book_id: str, summary: str, keywords: list[tuple[str, float]] | None = None
    ) -> None:
        """Reduce step: persists the whole-book summary plus its extracted
        content keywords (see pipelines/summary.py's run()/util/keywords.py),
        and marks the summarize task complete."""
        keyword_msgs = [mynexus_pb2.Keyword(term=term, weight=weight) for term, weight in (keywords or [])]
        self._stub.ReportBookSummary(
            mynexus_pb2.BookSummaryRequest(task_id=task_id, book_id=book_id, summary=summary, keywords=keyword_msgs)
        )

    def keyword_search(self, query: str, book_ids: list[str] | None, top_k: int) -> list[dict] | None:
        """Postgres-only GIN-indexed keyword search. Returns None (caller falls
        back to in-process BM25) on any RPC error — NOT_FOUND (sqlite backend,
        see grpcserver.CoreAPIServer.KeywordSearch) and UNAVAILABLE (Core API
        unreachable) are both handled the same way here."""
        try:
            resp = self._stub.KeywordSearch(
                mynexus_pb2.KeywordSearchRequest(query=query, book_ids=book_ids or [], top_k=top_k),
                timeout=10,
            )
        except grpc.RpcError:
            return None
        return [{"chunk_id": r.chunk_id, "book_id": r.book_id, "score": r.score} for r in resp.results]
