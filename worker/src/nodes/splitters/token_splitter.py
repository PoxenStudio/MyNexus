import logging
import uuid

from nodes.splitters.base_splitter import BaseSplitter
from schemas.document import Chunk, ParsedChapter
from util.tokens import count_tokens

logger = logging.getLogger(__name__)


class TokenSplitter(BaseSplitter):
    def __init__(self, chunk_size: int = 150, chunk_overlap: int = 30) -> None:
        self.chunk_size_chars = max(int(chunk_size), 1)
        self.chunk_overlap_chars = max(int(chunk_overlap), 0)

    @property
    def node_name(self) -> str:
        return "token_splitter"

    def process(self, book_id: str, chapters: list[ParsedChapter]) -> list[Chunk]:
        chunks: list[Chunk] = []
        position = 0
        step = max(self.chunk_size_chars - self.chunk_overlap_chars, 1)

        for chapter in chapters:
            text = chapter.content
            if not text:
                continue
            start = 0
            while start < len(text):
                raw = text[start : start + self.chunk_size_chars]
                piece = raw.strip()
                if piece:
                    lead = len(raw) - len(raw.lstrip())
                    trail = len(raw) - len(raw.rstrip())
                    chunks.append(
                        Chunk(
                            id=str(uuid.uuid4()),
                            book_id=book_id,
                            chapter_id=chapter.id,
                            content=piece,
                            position=position,
                            token_count=count_tokens(piece),
                            start_offset=start + lead,
                            end_offset=start + len(raw) - trail,
                        )
                    )
                    position += 1
                start += step

        logger.info(
            "split done: chapters=%d chunks=%d chunk_size_chars=%d chunk_overlap_chars=%d avg_tokens=%.1f",
            len(chapters),
            len(chunks),
            self.chunk_size_chars,
            self.chunk_overlap_chars,
            (sum(c.token_count for c in chunks) / len(chunks)) if chunks else 0.0,
        )
        return chunks


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m nodes.splitters.token_splitter path/to/book.epub
    import argparse

    from pipelines.ingestion import IngestionPipeline

    parser = argparse.ArgumentParser(description="Parse+clean a file, then split it and print chunk stats.")
    parser.add_argument("file_path")
    parser.add_argument("--chunk-size", type=int, default=150)
    parser.add_argument("--chunk-overlap", type=int, default=30)
    args = parser.parse_args()

    document = IngestionPipeline().parse_and_clean(args.file_path)
    splitter = TokenSplitter(args.chunk_size, args.chunk_overlap)
    result = splitter.process("cli-book", document.chapters)
    print(f"chapters={len(document.chapters)} chunks={len(result)}")
    for c in result[:5]:
        print(f"  [{c.position}] chapter={c.chapter_id} chars={len(c.content)} tokens={c.token_count} {c.content[:40]!r}...")
