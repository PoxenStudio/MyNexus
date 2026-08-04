import uuid

from nodes.splitters.base_splitter import BaseSplitter
from schemas.document import Chunk, ParsedChapter

# No tokenizer dependency (keeps the worker image small for NAS deployment,
# see docs/系统设计文档.md §3.4) — chars are used as a token-count approximation.
# CJK text runs close to 1 char ~= 1 token; English is closer to 4 chars ~= 1
# token, so this over-counts English token totals. Good enough for chunk
# sizing; swap in a real tokenizer here if precise counts matter later.
CHARS_PER_TOKEN = 1.0


class TokenSplitter(BaseSplitter):
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        self.chunk_size_chars = max(int(chunk_size * CHARS_PER_TOKEN), 1)
        self.chunk_overlap_chars = max(int(chunk_overlap * CHARS_PER_TOKEN), 0)

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
                piece = text[start : start + self.chunk_size_chars].strip()
                if piece:
                    chunks.append(
                        Chunk(
                            id=str(uuid.uuid4()),
                            book_id=book_id,
                            chapter_id=chapter.id,
                            content=piece,
                            position=position,
                            token_count=len(piece),
                        )
                    )
                    position += 1
                start += step

        return chunks


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m nodes.splitters.token_splitter path/to/book.epub
    import argparse

    from pipelines.ingestion import IngestionPipeline

    parser = argparse.ArgumentParser(description="Parse+clean a file, then split it and print chunk stats.")
    parser.add_argument("file_path")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    args = parser.parse_args()

    document = IngestionPipeline().parse_and_clean(args.file_path)
    splitter = TokenSplitter(args.chunk_size, args.chunk_overlap)
    result = splitter.process("cli-book", document.chapters)
    print(f"chapters={len(document.chapters)} chunks={len(result)}")
    for c in result[:5]:
        print(f"  [{c.position}] chapter={c.chapter_id} tokens~{c.token_count} {c.content[:40]!r}...")
