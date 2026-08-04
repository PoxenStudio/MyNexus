import json
import urllib.request
import uuid
from urllib.error import URLError

from config import WorkerConfig, load_config
from nodes.cleaners.whitespace_cleaner import WhitespaceCleaner
from nodes.factory import get_embedder, get_vector_store
from nodes.parsers.epub_parser import EpubParser
from nodes.parsers.registry import ParserRegistry
from nodes.parsers.txt_parser import TxtParser
from nodes.splitters.token_splitter import TokenSplitter
from schemas.document import ParsedDocument
from util.http import urlopen


def _post_json(url: str, payload: dict, timeout: float = 30) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            resp.read()
    except URLError as exc:
        raise RuntimeError(f"callback to {url} failed: {exc}") from exc


class IngestionPipeline:
    """Parse -> Clean -> Split -> Embed -> upsert into the vector store.

    `parse_and_clean` is the pure, HTTP-free core so it can run standalone from
    the CLI. `run` wraps the full pipeline with the progress/complete/fail
    callbacks Core API expects (docs/系统设计文档.md §2.3). Embedding and vector
    upsert happen here (Worker side); Core API only ever receives chunk
    *metadata* (no vectors) to persist — see .claude/memory/mynexus_m2_decisions.md
    for why Worker never writes to Core API's SQLite directly.
    """

    def __init__(self, config: WorkerConfig | None = None) -> None:
        self.config = config or load_config()
        self.parser_registry = ParserRegistry()
        self.parser_registry.register(EpubParser())
        self.parser_registry.register(TxtParser())
        self.cleaner = WhitespaceCleaner()
        self.splitter = TokenSplitter(self.config.splitter.chunk_size, self.config.splitter.chunk_overlap)
        self.embedder = get_embedder(self.config)
        self.vector_store = get_vector_store(self.config)

    def parse_and_clean(self, file_path: str, display_name: str = "") -> ParsedDocument:
        parser = self.parser_registry.get_parser(file_path)
        document = parser.process(file_path, display_name)
        for chapter in document.chapters:
            chapter.content = self.cleaner.process(chapter.content)
            if not chapter.id:
                chapter.id = str(uuid.uuid4())
        return document

    def run(self, task_id: str, book_id: str, file_path: str, callback_base_url: str, display_name: str = "") -> None:
        """Never raises: failures are reported via the /fail callback instead,
        since this runs inside a FastAPI BackgroundTask with no caller to catch it."""
        try:
            self._report_progress(callback_base_url, task_id, 10, "parsing")
            document = self.parse_and_clean(file_path, display_name)
            self._report_progress(callback_base_url, task_id, 40, "cleaning_done")

            chunks = self.splitter.process(book_id, document.chapters)
            self._report_progress(callback_base_url, task_id, 60, "splitting_done")

            if chunks:
                batch_size = 32
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i : i + batch_size]
                    vectors = self.embedder.process([c.content for c in batch])
                    self.vector_store.upsert(batch, vectors)
                    progress = 60 + int(35 * (i + len(batch)) / len(chunks))
                    self._report_progress(callback_base_url, task_id, min(progress, 95), "embedding")

            self._report_complete(callback_base_url, task_id, document, chunks)
        except Exception as exc:  # noqa: BLE001
            self._report_fail(callback_base_url, task_id, str(exc))

    def _report_progress(self, base_url: str, task_id: str, progress: int, stage: str, message: str = "") -> None:
        _post_json(
            f"{base_url.rstrip('/')}/internal/tasks/{task_id}/progress",
            {"progress": progress, "stage": stage, "message": message},
        )

    def _report_complete(self, base_url: str, task_id: str, document: ParsedDocument, chunks: list) -> None:
        payload = {
            "book": {"title": document.title, "author": document.author, "language": document.language},
            "chapters": [
                {"id": c.id, "title": c.title, "level": c.level, "sort_order": c.order, "content": c.content}
                for c in document.chapters
            ],
            "chunks": [
                {
                    "id": c.id,
                    "chapter_id": c.chapter_id,
                    "content": c.content,
                    "position": c.position,
                    "token_count": c.token_count,
                    "vector_id": c.id,  # local vector store keys by chunk id
                }
                for c in chunks
            ],
        }
        _post_json(f"{base_url.rstrip('/')}/internal/tasks/{task_id}/complete", payload)

    def _report_fail(self, base_url: str, task_id: str, error_msg: str) -> None:
        _post_json(f"{base_url.rstrip('/')}/internal/tasks/{task_id}/fail", {"error_msg": error_msg})


def build_status() -> dict:
    return {"status": "ready", "pipeline": "ingestion", "stages": ["parse", "clean", "split", "embed"]}


if __name__ == "__main__":
    # Standalone dry-run, no Core API/HTTP/embedding involved:
    #   python3 -m pipelines.ingestion path/to/book.epub
    import argparse

    parser = argparse.ArgumentParser(description="Dry-run the ingestion pipeline (parse + clean only).")
    parser.add_argument("file_path")
    args = parser.parse_args()

    doc = IngestionPipeline().parse_and_clean(args.file_path)
    print(f"title={doc.title!r} author={doc.author!r} chapters={len(doc.chapters)}")
    for c in doc.chapters:
        print(f"  [{c.order}] {c.title!r} ({len(c.content)} chars)")
