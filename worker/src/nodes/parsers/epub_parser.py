import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from nodes.parsers.base_parser import BaseParser
from schemas.document import ParsedChapter, ParsedDocument


class EpubParser(BaseParser):
    @property
    def node_name(self) -> str:
        return "epub_parser"

    @staticmethod
    def supported_formats() -> list[str]:
        return [".epub"]

    def process(self, file_path: str, display_name: str = "") -> ParsedDocument:
        book = epub.read_epub(file_path)

        title = self._meta(book, "title")
        author = self._meta(book, "creator")
        language = self._meta(book, "language")

        chapters: list[ParsedChapter] = []
        order = 0
        for idref, _linear in book.spine:
            item = book.get_item_with_id(idref)
            if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            if isinstance(item, (epub.EpubNav, epub.EpubNcx)):
                continue
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text("\n").strip()
            if not text:
                continue
            heading = soup.find(["h1", "h2", "h3"])
            chapter_title = heading.get_text().strip() if heading else (title or f"Chapter {order + 1}")
            chapters.append(ParsedChapter(title=chapter_title, level=1, order=order, content=text))
            order += 1

        if not chapters:
            chapters.append(ParsedChapter(title=title or "Untitled", level=1, order=0, content=""))

        return ParsedDocument(title=title, author=author, language=language, chapters=chapters)

    @staticmethod
    def _meta(book: "epub.EpubBook", name: str) -> str:
        values = book.get_metadata("DC", name)
        return values[0][0] if values else ""


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m nodes.parsers.epub_parser path/to/book.epub
    import argparse

    parser = argparse.ArgumentParser(description="Parse an EPUB file and print a chapter summary.")
    parser.add_argument("file_path")
    args = parser.parse_args()

    doc = EpubParser().process(args.file_path)
    print(f"title={doc.title!r} author={doc.author!r} language={doc.language!r} chapters={len(doc.chapters)}")
    for c in doc.chapters:
        print(f"  [{c.order}] {c.title!r} ({len(c.content)} chars)")
