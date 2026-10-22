"""Worker's network entrypoint — a gRPC server implementing WorkerService
(see proto/mynexus.proto). Replaces the earlier FastAPI+uvicorn HTTP server
(see .claude/memory/mynexus_grpc_migration.md): one persistent HTTP/2
connection per direction instead of one-shot HTTP/1.1 requests, binary
protobuf instead of JSON, and native streaming for Chat.
"""

from concurrent import futures
import logging
from logging.handlers import RotatingFileHandler
import math
import os
import socket
import sys
import threading
import uuid

import grpc

import mynexus_pb2
import mynexus_pb2_grpc
from config import load_config
from pipelines.ingestion import IngestionPipeline
from pipelines.qa import QAPipeline
from pipelines.retrieval import RetrievalPipeline
from pipelines.summary import SummaryPipeline


def _chat_message_dict(message) -> dict:
    data = {"role": message.role, "content": message.content}
    if message.HasField("context"):
        ctx = message.context
        payload = {}
        if ctx.HasField("reading"):
            r = ctx.reading
            payload["reading"] = {
                "book_title": r.book_title,
                "chapter_title": r.chapter_title,
                "chapter_href": r.chapter_href,
                "section_index": r.section_index,
                "progress_fraction": r.progress_fraction,
                "page": r.page,
                "cfi": r.cfi,
            }
        if ctx.HasField("selection"):
            s = ctx.selection
            payload["selection"] = {
                "text": s.text,
                "chapter_title": s.chapter_title,
                "chapter_href": s.chapter_href,
                "section_index": s.section_index,
                "page": s.page,
                "progress_fraction": s.progress_fraction,
                "cfi": s.cfi,
            }
        if payload:
            data["context"] = payload
    return data


class WorkerServicer(mynexus_pb2_grpc.WorkerServiceServicer):
    def __init__(self, cfg):
        self.ingestion = IngestionPipeline(cfg)
        self.retrieval = RetrievalPipeline(cfg)
        self.qa = QAPipeline(cfg)
        self.summary = SummaryPipeline(cfg)
        # task_id -> threading.Event for interrupting a running background
        # task (see CancelTask). Entries are added by TriggerSummarize and
        # removed when the run thread exits, so the dict can't leak entries
        # for finished tasks. Only summarize runs honor the flag today.
        self._cancel_events: dict[str, threading.Event] = {}
        self._cancel_lock = threading.Lock()

    def TriggerIngest(self, request, context):
        # Fire-and-forget in a background thread — mirrors the old FastAPI
        # BackgroundTasks behavior: the RPC returns immediately, and Worker
        # reports progress/completion/failure back via CoreApiClient calls
        # made from inside IngestionPipeline.run (see grpc_client.py).
        thread = threading.Thread(
            target=self.ingestion.run,
            args=(request.task_id, request.book_id, request.file_path, request.original_filename),
            daemon=True,
        )
        thread.start()
        return mynexus_pb2.IngestAck(accepted=True)

    def TriggerSummarize(self, request, context):
        # Same fire-and-forget pattern as TriggerIngest: returns immediately,
        # progress/chapter-summaries/completion/failure all come back via
        # CoreApiClient calls made from inside SummaryPipeline.run.
        cancel_event = threading.Event()
        with self._cancel_lock:
            self._cancel_events[request.task_id] = cancel_event

        def _run() -> None:
            try:
                self.summary.run(
                    request.task_id, request.book_id, list(request.chapters),
                    force_restart=request.force_restart, language=request.language,
                    cancel_event=cancel_event,
                )
            finally:
                with self._cancel_lock:
                    self._cancel_events.pop(request.task_id, None)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return mynexus_pb2.SummarizeAck(accepted=True)

    def CancelTask(self, request, context):
        with self._cancel_lock:
            event = self._cancel_events.get(request.task_id)
        if event is None:
            logging.info("cancel requested for unknown/inactive task %s", request.task_id)
            return mynexus_pb2.Ack(ok=False)
        event.set()
        logging.info("cancel flag set for task %s", request.task_id)
        return mynexus_pb2.Ack(ok=True)

    def Search(self, request, context):
        results = self.retrieval.search(
            request.query,
            book_ids=list(request.book_ids) or None,
            top_k=request.top_k or 10,
            score_threshold=request.score_threshold,
        )
        return mynexus_pb2.SearchResponse(
            results=[
                mynexus_pb2.SearchResult(
                    chunk_id=r["id"],
                    book_id=r["book_id"],
                    chapter_id=r["chapter_id"],
                    content=r["content"],
                    position=r["position"],
                    token_count=r["token_count"],
                    score=r["score"],
                )
                for r in results
            ]
        )

    def Chat(self, request, context):
        import json as _json

        messages = [_chat_message_dict(m) for m in request.messages]
        older_messages = [{"role": m.role, "content": m.content} for m in request.older_messages]
        book_ids = list(request.book_ids) or None
        top_k = request.top_k or 10

        for event in self.qa.answer(
            messages,
            book_ids=book_ids,
            top_k=top_k,
            memory_summary=request.memory_summary,
            memory_message_count=request.memory_message_count,
            older_messages=older_messages,
        ):
            if event["type"] == "delta":
                yield mynexus_pb2.ChatChunk(delta=event["content"])
            elif event["type"] == "memory_update":
                yield mynexus_pb2.ChatChunk(
                    memory_update=mynexus_pb2.MemoryUpdate(
                        summary=event["summary"], message_count=event["message_count"]
                    )
                )
            elif event["type"] == "tool_result":
                tr = mynexus_pb2.ToolResult(
                    tool_name=event["tool_name"],
                    result_json=_json.dumps(event["result"], ensure_ascii=False),
                )
                yield mynexus_pb2.ChatChunk(tool_result=tr)
            else:
                citations = [
                    mynexus_pb2.Citation(
                        chunk_id=c["chunk_id"],
                        chapter_id=c["chapter_id"],
                        book_id=c["book_id"],
                        score=c["score"],
                        content=c["content"],
                    )
                    for c in event["citations"]
                ]
                yield mynexus_pb2.ChatChunk(citations=mynexus_pb2.CitationList(items=citations))

    def ReembedBookSummary(self, request, context):
        # Synchronous — one embedding call, unlike TriggerIngest/
        # TriggerSummarize's fire-and-forget background jobs. See the rpc
        # comment in mynexus.proto and SummaryPipeline.reembed_book_summary.
        self.summary.reembed_book_summary(request.book_id, request.summary)
        return mynexus_pb2.Ack(ok=True)

    def DeleteBook(self, request, context):
        # Purges every vector-store record for this book_id — called by Core
        # API on book delete and before re-ingesting on rebuild, so ChromaDB/
        # SimpleVectorStore never keeps serving retrieval hits (and chat
        # citations) for a book that no longer has a books/chunks row (see
        # .claude/memory/mynexus_orphaned_vectors.md).
        self.retrieval.vector_store.delete_by_book(request.book_id)
        return mynexus_pb2.Ack(ok=True)

    def ExportBookVectors(self, request, context):
        offset = 0
        batch_size = 128
        while context.is_active():
            records = self.retrieval.vector_store.export_by_book(request.book_id, offset, batch_size)
            if not records:
                return
            for record in records:
                yield mynexus_pb2.VectorRecord(
                    id=record["id"],
                    book_id=record["book_id"],
                    chapter_id=record["chapter_id"],
                    content=record["content"],
                    position=record["position"],
                    token_count=record["token_count"],
                    start_offset=record["start_offset"],
                    end_offset=record["end_offset"],
                    embedding=record["vector"],
                )
            offset += len(records)

    def ImportBookVectors(self, request_iterator, context):
        staging_book_id = ""
        dimension = 0
        batch = []
        try:
            for record in request_iterator:
                if not staging_book_id:
                    staging_book_id = record.book_id
                elif record.book_id != staging_book_id:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "mixed staging book ids")
                embedding = list(record.embedding)
                if not embedding or not all(math.isfinite(value) for value in embedding):
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid vector embedding")
                if not dimension:
                    dimension = len(embedding)
                elif len(embedding) != dimension:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "mixed vector dimensions")
                batch.append(
                    {
                        "id": record.id,
                        "book_id": staging_book_id,
                        "chapter_id": record.chapter_id,
                        "content": record.content,
                        "position": record.position,
                        "token_count": record.token_count,
                        "start_offset": record.start_offset,
                        "end_offset": record.end_offset,
                        "vector": embedding,
                    }
                )
                if len(batch) >= 128:
                    self.retrieval.vector_store.import_records(staging_book_id, batch)
                    batch = []
            if batch:
                self.retrieval.vector_store.import_records(staging_book_id, batch)
        except Exception as exc:
            if staging_book_id:
                self.retrieval.vector_store.delete_by_book(staging_book_id)
            if isinstance(exc, grpc.RpcError):
                raise
            context.abort(grpc.StatusCode.INTERNAL, f"vector import failed: {exc}")
        return mynexus_pb2.Ack(ok=True)

    def CommitBookVectorImport(self, request, context):
        self.retrieval.vector_store.commit_import(
            request.book_id, request.staging_book_id, request.backup_book_id
        )
        return mynexus_pb2.Ack(ok=True)

    def RollbackBookVectorImport(self, request, context):
        self.retrieval.vector_store.rollback_import(
            request.book_id, request.staging_book_id, request.backup_book_id
        )
        return mynexus_pb2.Ack(ok=True)

    def FinalizeBookVectorImport(self, request, context):
        self.retrieval.vector_store.finalize_import(
            request.staging_book_id, request.backup_book_id
        )
        return mynexus_pb2.Ack(ok=True)

    def Shutdown(self, request, context):
        # Ack first, then exit shortly after on a separate thread so the
        # response actually reaches Core API before the process dies — see
        # the rpc comment in mynexus.proto for why this exists and what it
        # depends on (an external supervisor to restart the process). Exit
        # code 1 on purpose: docker-compose's `restart: unless-stopped` and
        # supervisord's `autorestart=true` both treat exit 0 as "voluntary
        # shutdown, don't bring it back", but this is a config-reload
        # cycle, so we want them to restart us.
        logging.info("shutdown requested via gRPC, exiting in 0.5s (exit code 1 for supervisor restart)")
        threading.Timer(0.5, lambda: os._exit(1)).start()
        return mynexus_pb2.Ack(ok=True)


def build_status() -> dict:
    return {"status": "ready", "pipeline": "worker-grpc", "stages": ["parse", "clean", "split", "embed"]}


def main():
    worker_id = f"{socket.gethostname()[:16]}-{uuid.uuid4().hex[:8]}"
    fmt = logging.Formatter(f"%(asctime)s %(levelname)s %(name)s [worker={worker_id}]: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(fmt)
    root.addHandler(stdout_handler)

    cfg = load_config()
    level = getattr(logging, cfg.log_level.strip().upper(), logging.INFO)
    root.setLevel(level)
    logging.info("worker starting: worker_id=%s pid=%d log_level=%s (config: %s)", worker_id, os.getpid(), logging.getLevelName(level), cfg.log_level)
    if cfg.log_dir:
        os.makedirs(cfg.log_dir, exist_ok=True)
        log_path = os.path.join(cfg.log_dir, "worker.log")
        file_handler = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=7, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
        logging.info("file logging enabled: %s", log_path)
    else:
        logging.info("file logging disabled (log_dir not configured)")
    # config.yaml is only ever read here, once, at process start (see
    # WorkerServicer.__init__ — every pipeline is constructed a single time
    # and reused for the process's whole lifetime). Editing config.yaml by
    # hand (as opposed to the system settings page, which restarts both
    # services) or restarting only Core API has zero effect on an
    # already-running Worker process until *it* is restarted too — logging
    # the config actually in effect here makes that mismatch obvious instead
    # of surfacing as a confusing "wrong provider" error deep in a pipeline
    # (see docs/Todos.md).
    logging.info(
        "effective config: embedding.provider=%s (%s) llm.provider=%s (%s) config_path=%s",
        cfg.embedding_provider,
        cfg.active_embedder.model,
        cfg.llm_provider,
        cfg.active_llm.model,
        os.getenv("MYNEXUS_CONFIG_PATH", "./config/config.yaml"),
    )
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max(cfg.max_concurrent_tasks, 1) + 4))
    mynexus_pb2_grpc.add_WorkerServiceServicer_to_server(WorkerServicer(cfg), server)
    server.add_insecure_port(f"[::]:{cfg.port}")
    server.start()
    print(f"worker grpc listening on :{cfg.port}")
    server.wait_for_termination()


if __name__ == "__main__":
    main()
