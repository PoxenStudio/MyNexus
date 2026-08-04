import re
from pathlib import Path

from nodes.parsers.base_parser import BaseParser
from schemas.document import ParsedChapter, ParsedDocument

# Matches common chapter headings in Chinese and English plain-text books,
# e.g. "第一章 ...", "第12回 ...", "Chapter 3 ...".
CHAPTER_PATTERN = re.compile(
    r"^\s*(第\s*[0-9一二三四五六七八九十百千]+\s*[章节回]|Chapter\s+\d+)\b.*$",
    re.IGNORECASE,
)


class TxtParser(BaseParser):
    @property
    def node_name(self) -> str:
        return "txt_parser"

    @staticmethod
    def supported_formats() -> list[str]:
        return [".txt"]

    def process(self, file_path: str, display_name: str = "") -> ParsedDocument:
        text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        title = Path(display_name).stem if display_name else Path(file_path).stem

        chapters = self._split_chapters(text, fallback_title=title)
        return ParsedDocument(title=title, author="", language="", chapters=chapters)

    @staticmethod
    def _split_chapters(text: str, fallback_title: str) -> list[ParsedChapter]:
        lines = text.splitlines()
        chapters: list[ParsedChapter] = []
        current_title = fallback_title
        current_lines: list[str] = []
        order = 0

        def flush():
            nonlocal current_lines, order
            content = "\n".join(current_lines).strip()
            if content:
                chapters.append(ParsedChapter(title=current_title, level=1, order=order, content=content))
                order += 1
            current_lines = []

        for line in lines:
            if CHAPTER_PATTERN.match(line):
                flush()
                current_title = line.strip()
            else:
                current_lines.append(line)
        flush()

        if not chapters:
            chapters.append(ParsedChapter(title=fallback_title, level=1, order=0, content=text.strip()))
        return chapters


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m nodes.parsers.txt_parser path/to/book.txt
    import argparse

    parser = argparse.ArgumentParser(description="Parse a TXT file and print a chapter summary.")
    parser.add_argument("file_path")
    args = parser.parse_args()

    doc = TxtParser().process(args.file_path)
    print(f"title={doc.title!r} chapters={len(doc.chapters)}")
    for c in doc.chapters:
        print(f"  [{c.order}] {c.title!r} ({len(c.content)} chars)")
