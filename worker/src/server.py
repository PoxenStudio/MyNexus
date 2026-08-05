"""Worker's network entrypoint — a gRPC server implementing WorkerService
(see proto/mynexus.proto). Replaces the earlier FastAPI+uvicorn HTTP server
(see .claude/memory/mynexus_grpc_migration.md): one persistent HTTP/2
connection per direction instead of one-shot HTTP/1.1 requests, binary
protobuf instead of JSON, and native streaming for Chat.
"""

from concurrent import futures
import threading

import grpc

import mynexus_pb2
import mynexus_pb2_grpc
from config import load_config
from pipelines.ingestion import IngestionPipeline
from pipelines.qa import QAPipeline
from pipelines.retrieval import RetrievalPipeline


class WorkerServicer(mynexus_pb2_grpc.WorkerServiceServicer):
    def __init__(self, cfg):
        self.ingestion = IngestionPipeline(cfg)
        self.retrieval = RetrievalPipeline(cfg)
        self.qa = QAPipeline(cfg)

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


def build_status() -> dict:
    return {"status": "ready", "pipeline": "worker-grpc", "stages": ["parse", "clean", "split", "embed"]}


def main():
    cfg = load_config()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max(cfg.max_concurrent_tasks, 1) + 4))
    mynexus_pb2_grpc.add_WorkerServiceServicer_to_server(WorkerServicer(cfg), server)
    server.add_insecure_port(f"[::]:{cfg.port}")
    server.start()
    print(f"worker grpc listening on :{cfg.port}")
    server.wait_for_termination()


if __name__ == "__main__":
    main()
