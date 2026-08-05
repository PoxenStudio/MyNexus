import logging
import uuid

from config import WorkerConfig, load_config
from grpc_client import CoreApiClient
from nodes.cleaners.whitespace_cleaner import WhitespaceCleaner
from nodes.factory import get_embedder, get_vector_store
from nodes.parsers.epub_parser import EpubParser
from nodes.parsers.registry import ParserRegistry
from nodes.parsers.txt_parser import TxtParser
from nodes.splitters.token_splitter import TokenSplitter
from schemas.document import ParsedDocument

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Parse -> Clean -> Split -> Embed -> upsert into the vector store.

    `parse_and_clean` is the pure, gRPC-free core so it can run standalone
    from the CLI. `run` wraps the full pipeline with the progress/complete/fail
    calls Core API expects (docs/系统设计文档.md §2.3, now gRPC — see
    .claude/memory/mynexus_grpc_migration.md). Embedding and vector upsert
    happen here (Worker side); Core API only ever receives chunk *metadata*
    (no vectors) to persist — see .claude/memory/mynexus_m2_decisions.md for
    why Worker never writes to Core API's database directly.
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
        self.core_api = CoreApiClient(self.config)

    def parse_and_clean(self, file_path: str, display_name: str = "") -> ParsedDocument:
        parser = self.parser_registry.get_parser(file_path)
        document = parser.process(file_path, display_name)
        for chapter in document.chapters:
            chapter.content = self.cleaner.process(chapter.content)
            if not chapter.id:
                chapter.id = str(uuid.uuid4())
        return document

    def run(self, task_id: str, book_id: str, file_path: str, display_name: str = "") -> None:
        """Never raises: failures are reported via report_fail instead, since
        this runs inside a background thread with no caller to catch it (see
        server.py's TriggerIngest)."""
        try:
            self.core_api.report_progress(task_id, 10, "parsing")
            # parse_and_clean is also the file-legality check: a corrupt/
            # unsupported file raises here (e.g. EpubParser's epub.read_epub)
            # before anything else runs.
            document = self.parse_and_clean(file_path, display_name)
            self.core_api.report_progress(task_id, 25, "metadata_done")
            # Persist title/author/language now, independent of whether the
            # slower/more failure-prone splitting+embedding stages below
            # succeed, so the book's info is never stuck blank because of an
            # unrelated failure (e.g. an embedding API error) later on.
            self.core_api.report_metadata(task_id, document)
            self.core_api.report_progress(task_id, 40, "cleaning_done")

            chunks = self.splitter.process(book_id, document.chapters)
            self.core_api.report_progress(task_id, 60, "splitting_done")

            if chunks:
                batch_size = 32
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i : i + batch_size]
                    vectors = self.embedder.process([c.content for c in batch])
                    self.vector_store.upsert(batch, vectors)
                    progress = 60 + int(35 * (i + len(batch)) / len(chunks))
                    self.core_api.report_progress(task_id, min(progress, 95), "embedding")

            self.core_api.report_complete(task_id, document, chunks)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ingestion failed (task_id=%s book_id=%s file_path=%s)", task_id, book_id, file_path)
            self.core_api.report_fail(task_id, str(exc))


def build_status() -> dict:
    return {"status": "ready", "pipeline": "ingestion", "stages": ["parse", "clean", "split", "embed"]}


if __name__ == "__main__":
    # Standalone dry-run, no Core API/gRPC/embedding involved:
    #   python3 -m pipelines.ingestion path/to/book.epub
    import argparse

    parser = argparse.ArgumentParser(description="Dry-run the ingestion pipeline (parse + clean only).")
    parser.add_argument("file_path")
    args = parser.parse_args()

    doc = IngestionPipeline().parse_and_clean(args.file_path)
    print(f"title={doc.title!r} author={doc.author!r} chapters={len(doc.chapters)}")
    for c in doc.chapters:
        print(f"  [{c.order}] {c.title!r} ({len(c.content)} chars)")
