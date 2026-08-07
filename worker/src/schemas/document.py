from dataclasses import dataclass, field


@dataclass
class ParsedChapter:
    id: str = ""
    title: str = ""
    level: int = 1
    order: int = 0
    content: str = ""


@dataclass
class ParsedDocument:
    title: str = ""
    author: str = ""
    language: str = ""
    chapters: list[ParsedChapter] = field(default_factory=list)
    # Cover image bytes, if the parser found one embedded in the source file
    # (currently EPUB only — see nodes.parsers.epub_parser._extract_cover;
    # TxtParser never sets this, TXT has no embedded images). Empty if none —
    # ingestion.py's run() fills this in with a title-generated fallback
    # (util/cover_generator.py) when it's still empty after parsing.
    cover: bytes = b""
    # MIME type of `cover` (e.g. "image/jpeg"); empty iff cover is empty.
    cover_content_type: str = ""


@dataclass
class Chunk:
    id: str = ""
    book_id: str = ""
    chapter_id: str = ""
    content: str = ""
    position: int = 0
    token_count: int = 0
