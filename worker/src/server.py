import json

import uvicorn
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import load_config
from pipelines.ingestion import IngestionPipeline, build_status
from pipelines.qa import QAPipeline
from pipelines.retrieval import RetrievalPipeline

cfg = load_config()
app = FastAPI(title="MyNexus Worker")
ingestion_pipeline = IngestionPipeline(cfg)
retrieval_pipeline = RetrievalPipeline(cfg)
qa_pipeline = QAPipeline(cfg)


class IngestRequest(BaseModel):
    task_id: str
    book_id: str
    file_path: str
    callback_base_url: str
    original_filename: str = ""


class SearchRequest(BaseModel):
    query: str
    book_ids: list[str] = []
    top_k: int = 10
    score_threshold: float = 0.0


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    book_ids: list[str] = []
    top_k: int = 5


@app.get("/health")
@app.get("/internal/health")
def health():
    return {"status": "ok", "service": "worker"}


@app.get("/internal/pipeline")
def pipeline_status():
    return build_status()


@app.post("/internal/ingest", status_code=202)
def ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        ingestion_pipeline.run, req.task_id, req.book_id, req.file_path, req.callback_base_url, req.original_filename
    )
    return {"accepted": True, "task_id": req.task_id}


@app.post("/internal/search")
def search(req: SearchRequest):
    results = retrieval_pipeline.search(
        req.query, book_ids=req.book_ids or None, top_k=req.top_k, score_threshold=req.score_threshold
    )
    return {"results": results}


@app.post("/internal/chat")
def chat(req: ChatRequest):
    messages = [m.model_dump() for m in req.messages]

    def event_stream():
        for event in qa_pipeline.answer(messages, book_ids=req.book_ids or None, top_k=req.top_k):
            if event["type"] == "delta":
                chunk = {"choices": [{"delta": {"content": event["content"]}}]}
            else:
                chunk = {"choices": [{"delta": {}}], "citations": event["citations"]}
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def main():
    print(f"worker listening on :{cfg.port}")
    uvicorn.run(app, host="0.0.0.0", port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
