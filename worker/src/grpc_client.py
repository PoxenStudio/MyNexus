"""Worker's gRPC client to Core API's CoreApiService — replaces the old
urllib-based HTTP callbacks (task progress/complete/fail) and the keyword
search HTTP call added for the Postgres GIN work. See
.claude/memory/mynexus_grpc_migration.md and mynexus_keyword_search_gin.md.
"""

import grpc
import logging

import mynexus_pb2
import mynexus_pb2_grpc
from config import WorkerConfig


def _friendly_error(msg: str) -> str:
    """Map low-level network/LLM transport errors to a short user-facing message.

    Strategy:
    1. If the original message already contains domain keywords ("LLM"/"嵌入"/
       "向量"...) worker itself has already produced a readable Chinese error
       (see util/http.py's ServiceCallError) — keep it as-is so we don't mask
       a precise "LLM 服务不可用" with a generic fallback.
    2. Otherwise fall back to keyword matching against raw English stack
       traces (requests exceptions, httpx, socket errors...) that leak through
       when no ServiceCallError wrapper caught them.
    3. Unmatched errors pass through unchanged.
    """
    if any(kw in msg for kw in ("LLM", "嵌入", "向量", "分块", "检索", "连接超时")):
        return msg
    lower = msg.lower()
    if "connection refused" in lower or "failed to establish" in lower or "newconnectionerror" in lower:
        return "LLM 服务无法连接，请确认模型服务（Ollama / OpenAI 兼容端点）已启动"
    if "max retries exceeded" in lower or "connecterror" in lower:
        return "LLM 服务连接失败，请检查模型服务地址是否可达"
    if "readtimeout" in lower or "connecttimeout" in lower or "timed out" in lower:
        return "LLM 服务响应超时，请稍后重试或检查网络"
    if "httpx" in lower and ("connect" in lower or "network" in lower):
        return "LLM 服务网络异常，请稍后重试"
    if "api_connection_error" in lower or "apiconnectionerror" in lower:
        return "LLM API 连接失败，请检查网络或 API 端点配置"
    if "authenticationerror" in lower or "invalid api key" in lower or "401" in lower:
        return "LLM API 密钥无效，请检查系统配置中的 API Key"
    if "rate limit" in lower or "ratelimit" in lower or "429" in lower:
        return "LLM API 调用频率超限，请稍后重试"
    if "context length" in lower or ("max_tokens" in lower and "exceed" in lower):
        return "LLM 输入超出上下文长度限制"
    return msg


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
                start_offset=c.start_offset,
                end_offset=c.end_offset,
            )
            for c in chunks
        ]
        self._stub.ReportComplete(
            mynexus_pb2.CompleteRequest(
                task_id=task_id, book=book, chapters=chapters, chunks=chunk_msgs,
                cover=document.cover, cover_content_type=document.cover_content_type,
            )
        )

    def report_fail(self, task_id: str, error_msg: str, canceled: bool = False) -> None:
        self._stub.ReportFail(
            mynexus_pb2.FailRequest(task_id=task_id, error_msg=_friendly_error(error_msg), canceled=canceled)
        )

    def report_chapter_summary(
        self,
        task_id: str,
        chapter_id: str,
        summary: str,
        keywords: list[tuple[str, float]] | None = None,
        definitions: list[tuple[str, str]] | None = None,
    ) -> None:
        """Map step of summarization (see pipelines/summary.py): persists one
        chapter's summary immediately, so progress survives a mid-run crash.

        keywords: this chapter's own top-N content keywords (distinct from
        report_book_summary's whole-book aggregate). definitions: {name,
        content} pairs the chapter itself defines, LLM-extracted."""
        keyword_msgs = [mynexus_pb2.Keyword(term=term, weight=weight) for term, weight in (keywords or [])]
        definition_msgs = [mynexus_pb2.Definition(name=name, content=content) for name, content in (definitions or [])]
        self._stub.ReportChapterSummary(
            mynexus_pb2.ChapterSummaryRequest(
                task_id=task_id,
                chapter_id=chapter_id,
                summary=summary,
                keywords=keyword_msgs,
                definitions=definition_msgs,
            )
        )

    def report_book_summary(
        self, task_id: str, book_id: str, summary: str, keywords: list[tuple[str, float]] | None = None,
        reading_guide: str = "", reference_index: str = "",
    ) -> None:
        keyword_msgs = [mynexus_pb2.Keyword(term=term, weight=weight) for term, weight in (keywords or [])]
        self._stub.ReportBookSummary(
            mynexus_pb2.BookSummaryRequest(
                task_id=task_id, book_id=book_id, summary=summary, keywords=keyword_msgs,
                reading_guide=reading_guide, reference_index=reference_index,
            )
        )

    def report_token_usage(
        self,
        task_id: str,
        book_id: str,
        task_type: str,
        llm_provider: str,
        llm_model: str,
        call_site: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        """Fire-and-forget accounting for one LLM call's usage — a failed
        report is logged but never aborts the summarize/ingest task that
        was actually doing useful work. See mynexus.proto ReportTokenUsage."""
        try:
            self._stub.ReportTokenUsage(
                mynexus_pb2.TokenUsageRequest(
                    task_id=task_id,
                    book_id=book_id,
                    task_type=task_type,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    call_site=call_site,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                ),
                timeout=5,
            )
        except grpc.RpcError as e:
            logging.getLogger(__name__).warning("report_token_usage failed: %v", e)

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

    def get_library_stats(self) -> dict | None:
        """Backs the chat "get_library_stats" tool (see tools/library_stats.py
        and .claude/memory/mynexus_chat_tool_calling.md). Returns None on any
        RPC error — the tool then reports it couldn't fetch the stats rather
        than raising and aborting the whole chat turn."""
        try:
            resp = self._stub.GetLibraryStats(mynexus_pb2.LibraryStatsRequest(), timeout=10)
        except grpc.RpcError:
            return None
        return {
            "total_books": resp.total_books,
            "by_status": {c.status: c.count for c in resp.by_status},
        }

    def get_chapter_content(self, book_id: str, chapter_id: str) -> dict | None:
        """Backs the chat "read_chapter" tool (see tools/read_chapter.py).
        Returns None on any RPC error — the tool then reports it couldn't
        fetch the chapter rather than raising and aborting the whole chat
        turn."""
        try:
            resp = self._stub.GetChapterContent(
                mynexus_pb2.ChapterContentRequest(book_id=book_id, chapter_id=chapter_id), timeout=10
            )
        except grpc.RpcError:
            return None
        return {
            "chapter_id": resp.chapter_id,
            "title": resp.title,
            "content": resp.content,
            "sort_order": resp.sort_order,
        }

    def get_book_info(self, query: str) -> list[dict] | None:
        """Backs the chat "get_book_info" tool (see tools/book_info.py).
        Returns None on any RPC error — the tool then reports it couldn't
        fetch the info rather than raising and aborting the whole chat
        turn."""
        try:
            resp = self._stub.GetBookInfo(mynexus_pb2.BookInfoRequest(query=query), timeout=10)
        except grpc.RpcError:
            return None
        return [
            {
                "book_id": b.book_id,
                "title": b.title,
                "author": b.author,
                "publisher": b.publisher,
                "category": b.category,
                "tags": list(b.tags),
                "summary": b.summary,
                "chapters": [
                    {
                        "chapter_id": c.chapter_id,
                        "title": c.title,
                        "summary": c.summary,
                        "sort_order": c.sort_order,
                    }
                    for c in b.chapters
                ],
            }
            for b in resp.books
        ]

    def get_chapter_summaries(self, book_id: str) -> dict | None:
        """Backs IngestionPipeline's post-ingest re-embed pass (see
        pipelines/ingestion.py): the chapter summaries + whole-book summary
        that survive a rebuild in Core API's database (SaveChapters carries
        them over by title) but whose vector-store records were wiped by
        Worker's own delete_by_book. Returns None on any RPC error — the
        re-embed pass is best-effort and must never fail the ingest."""
        try:
            resp = self._stub.GetChapterSummaries(
                mynexus_pb2.ChapterSummariesRequest(book_id=book_id), timeout=30
            )
        except grpc.RpcError:
            logging.getLogger(__name__).warning("get_chapter_summaries RPC failed for book %s", book_id)
            return None
        return {
            "chapters": [{"chapter_id": c.chapter_id, "summary": c.summary} for c in resp.chapters],
            "book_summary": resp.book_summary,
        }
