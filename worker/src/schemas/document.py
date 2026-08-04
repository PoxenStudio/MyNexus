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


@dataclass
class Chunk:
    id: str = ""
    book_id: str = ""
    chapter_id: str = ""
    content: str = ""
    position: int = 0
    token_count: int = 0
