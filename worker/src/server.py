"""Worker's network entrypoint — a gRPC server implementing WorkerService
(see proto/mynexus.proto). Replaces the earlier FastAPI+uvicorn HTTP server
(see .claude/memory/mynexus_grpc_migration.md): one persistent HTTP/2
connection per direction instead of one-shot HTTP/1.1 requests, binary
protobuf instead of JSON, and native streaming for Chat.
"""

from concurrent import futures
import logging
import os
import threading

import grpc

import mynexus_pb2
import mynexus_pb2_grpc
from config import load_config
from pipelines.ingestion import IngestionPipeline
from pipelines.qa import QAPipeline
from pipelines.retrieval import RetrievalPipeline
from pipelines.summary import SummaryPipeline


class WorkerServicer(mynexus_pb2_grpc.WorkerServiceServicer):
    def __init__(self, cfg):
        self.ingestion = IngestionPipeline(cfg)
        self.retrieval = RetrievalPipeline(cfg)
        self.qa = QAPipeline(cfg)
        self.summary = SummaryPipeline(cfg)

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
        thread = threading.Thread(
            target=self.summary.run,
            args=(request.task_id, request.book_id, list(request.chapters)),
            kwargs={"force_restart": request.force_restart, "language": request.language},
            daemon=True,
        )
        thread.start()
        return mynexus_pb2.SummarizeAck(accepted=True)

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
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        book_ids = list(request.book_ids) or None
        top_k = request.top_k or 5

        for event in self.qa.answer(messages, book_ids=book_ids, top_k=top_k):
            if event["type"] == "delta":
                yield mynexus_pb2.ChatChunk(delta=event["content"])
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

    def DeleteBook(self, request, context):
        # Purges every vector-store record for this book_id — called by Core
        # API on book delete and before re-ingesting on rebuild, so ChromaDB/
        # SimpleVectorStore never keeps serving retrieval hits (and chat
        # citations) for a book that no longer has a books/chunks row (see
        # .claude/memory/mynexus_orphaned_vectors.md).
        self.retrieval.vector_store.delete_by_book(request.book_id)
        return mynexus_pb2.Ack(ok=True)

    def Shutdown(self, request, context):
        # Ack first, then exit shortly after on a separate thread so the
        # response actually reaches Core API before the process dies — see
        # the rpc comment in mynexus.proto for why this exists and what it
        # depends on (an external supervisor to restart the process).
        logging.info("shutdown requested via gRPC, exiting in 0.5s")
        threading.Timer(0.5, lambda: os._exit(0)).start()
        return mynexus_pb2.Ack(ok=True)


def build_status() -> dict:
    return {"status": "ready", "pipeline": "worker-grpc", "stages": ["parse", "clean", "split", "embed"]}


def main():
    # Pipelines log failures (e.g. ingestion.py's exception handler) via the
    # stdlib logging module; without a handler configured those are silently
    # dropped instead of showing up in .tmp/worker.log.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
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
