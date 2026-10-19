from dataclasses import dataclass
from pathlib import Path

import pymupdf

from nodes.parsers.base_parser import BaseParser
from schemas.document import ParsedChapter, ParsedDocument


@dataclass(frozen=True)
class _TextBlock:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


class PdfParser(BaseParser):
    @property
    def node_name(self) -> str:
        return "pdf_parser"

    @staticmethod
    def supported_formats() -> list[str]:
        return [".pdf"]

    def process(self, file_path: str, display_name: str = "") -> ParsedDocument:
        with pymupdf.open(file_path) as pdf:
            if pdf.needs_pass:
                raise ValueError("encrypted PDFs are not supported")

            page_texts = [self._extract_page_text(page) for page in pdf]
            metadata = pdf.metadata or {}

        text = "\n\n".join(page_text for page_text in page_texts if page_text).strip()
        if not text:
            raise ValueError("PDF contains no extractable text; scanned PDFs are not supported")

        title = (metadata.get("title") or "").strip()
        if not title:
            title = Path(display_name or file_path).stem

        return ParsedDocument(
            title=title,
            author=(metadata.get("author") or "").strip(),
            language=(metadata.get("language") or "").strip(),
            chapters=[ParsedChapter(title=title, level=1, order=0, content=text)],
        )

    @classmethod
    def _extract_page_text(cls, page: pymupdf.Page) -> str:
        blocks = [
            _TextBlock(
                x0=block[0],
                y0=block[1],
                x1=block[2],
                y1=block[3],
                text=block[4].strip(),
            )
            for block in page.get_text("blocks", sort=False)
            if len(block) >= 7 and block[6] == 0 and block[4].strip()
        ]
        if not blocks:
            return ""

        ordered: list[_TextBlock] = []
        group: list[_TextBlock] = []
        full_width_threshold = page.rect.width * 0.72

        for block in sorted(blocks, key=lambda item: (item.y0, item.x0)):
            if block.x1 - block.x0 >= full_width_threshold:
                ordered.extend(cls._order_column_group(group, page.rect.width, page.rect.height))
                group = []
                ordered.append(block)
            else:
                group.append(block)
        ordered.extend(cls._order_column_group(group, page.rect.width, page.rect.height))
        return "\n\n".join(block.text for block in ordered)

    @staticmethod
    def _order_column_group(
        blocks: list[_TextBlock], page_width: float, page_height: float
    ) -> list[_TextBlock]:
        if len(blocks) < 4:
            return sorted(blocks, key=lambda item: (item.y0, item.x0))

        intervals = sorted((block.x0, block.x1) for block in blocks)
        spans: list[list[float]] = []
        for start, end in intervals:
            if spans and start <= spans[-1][1]:
                spans[-1][1] = max(spans[-1][1], end)
            else:
                spans.append([start, end])

        gap_threshold = page_width * 0.035
        columns: list[list[_TextBlock]] = [[]]
        for index, span in enumerate(spans):
            if index > 0 and span[0] - spans[index - 1][1] >= gap_threshold:
                columns.append([])
            columns[-1].extend(
                block for block in blocks if span[0] <= (block.x0 + block.x1) / 2 <= span[1]
            )

        if len(columns) < 2 or any(len(column) < 2 for column in columns):
            return sorted(blocks, key=lambda item: (item.y0, item.x0))

        top = max(min(block.y0 for block in column) for column in columns)
        bottom = min(max(block.y1 for block in column) for column in columns)
        if bottom - top < page_height * 0.12:
            return sorted(blocks, key=lambda item: (item.y0, item.x0))

        return [
            block
            for column in columns
            for block in sorted(column, key=lambda item: (item.y0, item.x0))
        ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse a text-based PDF and print a summary.")
    parser.add_argument("file_path")
    args = parser.parse_args()

    doc = PdfParser().process(args.file_path)
    print(f"title={doc.title!r} author={doc.author!r} chapters={len(doc.chapters)}")
    for chapter in doc.chapters:
        print(f"  [{chapter.order}] {chapter.title!r} ({len(chapter.content)} chars)")
