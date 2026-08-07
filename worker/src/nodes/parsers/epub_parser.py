import logging
import os
import posixpath
import re
import tempfile
import zipfile
from urllib.parse import unquote

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub
from lxml import etree

from nodes.parsers.base_parser import BaseParser
from schemas.document import ParsedChapter, ParsedDocument

logger = logging.getLogger(__name__)

# Elements whose text extraction/newline-joining rules changed here — see
# _extract_text's doc comment.
_BLOCK_TAGS = ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "td", "th"]

_OPF_NS = "http://www.idpf.org/2007/opf"
_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"


class EpubParser(BaseParser):
    @property
    def node_name(self) -> str:
        return "epub_parser"

    @staticmethod
    def supported_formats() -> list[str]:
        return [".epub"]

    def process(self, file_path: str, display_name: str = "") -> ParsedDocument:
        book = self._read_epub(file_path)

        title = self._meta(book, "title")
        author = self._meta(book, "creator")
        language = self._meta(book, "language")

        # book.toc (from the EPUB3 nav doc or the EPUB2 toc.ncx — ebooklib
        # abstracts over both) is the publisher's own declaration of what
        # counts as a chapter. Trusting it over raw spine order matters
        # because the spine also carries front-matter documents (half-title
        # page, blank separator pages, ...) that the TOC doesn't link to —
        # without this, a half-title page whose only text is the book's own
        # title (nothing to summarize) turned into a bogus one-line
        # "chapter" (see docs/Todos.md). Falls back to the pre-fix "every
        # non-empty spine doc is a chapter" behavior when a book has no
        # TOC at all (e.g. some plain EPUB2 without toc.ncx).
        toc_titles = self._toc_titles(book)

        chapters: list[ParsedChapter] = []
        order = 0
        for idref, _linear in book.spine:
            item = book.get_item_with_id(idref)
            if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            if isinstance(item, (epub.EpubNav, epub.EpubNcx)):
                continue
            href_key = _href_key(item.get_name())
            if toc_titles and href_key not in toc_titles:
                continue
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = self._extract_text(soup)
            if not text:
                continue
            heading = soup.find(["h1", "h2", "h3"])
            # The TOC's own title wins when we have one — it's the fuller,
            # publisher-authored title (e.g. "第一章 “机会平等”谬误")
            # vs. whatever heading tag (if any) happens to be first in the
            # document (often just "第一章").
            chapter_title = (
                toc_titles.get(href_key)
                or (heading.get_text().strip() if heading else None)
                or title
                or f"Chapter {order + 1}"
            )
            chapters.append(ParsedChapter(title=chapter_title, level=1, order=order, content=text))
            order += 1

        if not chapters:
            chapters.append(ParsedChapter(title=title or "Untitled", level=1, order=0, content=""))

        cover, cover_content_type = self._extract_cover(book)
        return ParsedDocument(
            title=title, author=author, language=language, chapters=chapters,
            cover=cover, cover_content_type=cover_content_type,
        )

    @staticmethod
    def _read_epub(file_path: str) -> "epub.EpubBook":
        """epub.read_epub aborts the *entire* parse the moment any manifest
        item's href points at a file that isn't actually a member of the zip
        archive — ebooklib does a bare self.zf.read(name) with no
        try/except in EpubReader._load_manifest, so one dangling reference
        (e.g. a cover thumbnail declared in content.opf but never actually
        packaged) takes down an otherwise-readable book with a raw
        KeyError. Real-world/non-standard EPUBs hit this occasionally, so
        rather than failing the whole book, repair the manifest by
        dropping entries that don't resolve to a real zip member and retry
        once before giving up."""
        try:
            return epub.read_epub(file_path)
        except KeyError:
            repaired_path = EpubParser._repair_missing_manifest_items(file_path)
            if repaired_path is None:
                raise
            try:
                return epub.read_epub(repaired_path)
            finally:
                os.unlink(repaired_path)

    @staticmethod
    def _repair_missing_manifest_items(file_path: str) -> str | None:
        """Rewrites the OPF's <manifest> (and any matching <spine>
        itemrefs) to drop items whose href isn't an actual member of the
        zip archive, writing the result to a new temp .epub whose path is
        returned. Returns None — "give up, nothing to repair" — if the
        zip/OPF can't even be parsed, or if every manifest item did
        resolve (the KeyError that triggered this must have come from
        something else, e.g. a genuinely corrupt zip)."""
        try:
            with zipfile.ZipFile(file_path) as zf:
                names = set(zf.namelist())
                container = etree.fromstring(zf.read("META-INF/container.xml"))
                rootfile = container.find(f".//{{{_CONTAINER_NS}}}rootfile")
                opf_path = rootfile.get("full-path")
                opf_dir = posixpath.dirname(opf_path)
                opf_root = etree.fromstring(zf.read(opf_path))

                manifest = opf_root.find(f"{{{_OPF_NS}}}manifest")
                if manifest is None:
                    return None

                missing_ids = set()
                for item in list(manifest):
                    href = item.get("href")
                    if href is None:
                        continue
                    item_path = posixpath.join(opf_dir, unquote(href))
                    if item_path not in names:
                        missing_ids.add(item.get("id"))
                        manifest.remove(item)

                if not missing_ids:
                    return None

                spine = opf_root.find(f"{{{_OPF_NS}}}spine")
                if spine is not None:
                    for itemref in list(spine):
                        if itemref.get("idref") in missing_ids:
                            spine.remove(itemref)

                logger.warning(
                    "epub %s: dropping %d manifest item(s) missing from the archive: %s",
                    file_path, len(missing_ids), ", ".join(sorted(i for i in missing_ids if i)),
                )

                opf_bytes = etree.tostring(opf_root, xml_declaration=True, encoding="utf-8")

                fd, tmp_path = tempfile.mkstemp(suffix=".epub")
                os.close(fd)
                with zipfile.ZipFile(file_path) as src, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as dst:
                    for zinfo in src.infolist():
                        data = opf_bytes if zinfo.filename == opf_path else src.read(zinfo.filename)
                        dst.writestr(zinfo, data)
                return tmp_path
        except Exception:
            logger.warning("epub %s: manifest repair failed, giving up", file_path, exc_info=True)
            return None

    @staticmethod
    def _extract_text(soup: BeautifulSoup) -> str:
        """Was `soup.get_text("\\n").strip()` — joined *every* text node in
        the document with "\\n", with no regard for whether two text nodes
        were actually different paragraphs or just adjacent inline runs
        within the same line. Chinese ebook typesetting commonly wraps each
        character of a title in its own inline tag for letter-spacing (e.g.
        `<h1><b>译</b><b>者</b><b>序</b></h1>`, renders as one line "译者序"
        in a browser since `<b>` is inline) — the old code turned every one
        of those into a bogus line break ("译\\n者\\n序"), which then went
        straight into the LLM prompt as if it were real structure (see
        docs/Todos.md).

        Fixed by only inserting a newline *between* block-level elements,
        never within one: walk every leaf block element (one with no
        block-level descendant of its own — skipping non-leaf ones avoids
        double-counting a `<div>` that merely wraps `<p>`s), and get_text()
        each with no separator so inline siblings (bold/span/etc. runs)
        concatenate directly, the way a browser would actually render them.

        Also drops `<aside>` elements first — EPUB/HTML5 footnotes and
        endnotes are marked up as `<aside epub:type="footnote">` sitting
        right in the reading-order flow, and the old whole-document
        get_text() pulled their text (raw bibliographic citations, not the
        author's own argument) inline into the chapter body — see
        docs/Todos.md for how much this was diluting long chapters that
        already get truncated for the summarizer.

        Within a block, runs of whitespace are collapsed to one space
        (matching how a browser renders HTML whitespace) rather than kept
        verbatim: a footnote *marker* like `<sup><a epub:type="noteref">
        <img .../></a></sup>` sitting mid-sentence carries no visible text of
        its own, but the pretty-printed source's indentation around it
        (`\n\t` before the tag, a stray literal space before `<img>`) is a
        real whitespace-only text node that get_text() would otherwise
        splice into the sentence verbatim — "...意涵。\n\t 在卢梭所展望..."
        (that "\t" is what shows up as a run of spaces once printed/viewed,
        not actually several space characters). `<pre>` is exempt since
        there whitespace is the actual content, not source formatting.
        """
        for aside in soup.find_all("aside"):
            aside.decompose()

        blocks = []
        for el in soup.find_all(_BLOCK_TAGS):
            if el.find(_BLOCK_TAGS):
                continue  # not a leaf — its text is captured via its block-level children instead
            text = el.get_text()
            if el.name != "pre":
                text = re.sub(r"\s+", " ", text)
            text = text.strip()
            if text:
                blocks.append(text)
        return "\n".join(blocks)

    @staticmethod
    def _extract_cover(book: "epub.EpubBook") -> tuple[bytes, str]:
        """Best-effort cover lookup, in the order real-world EPUBs actually
        expose one:
          1. Items ebooklib itself classifies as ITEM_COVER — EPUB3's
             `<item properties="cover-image">` manifest entry.
          2. EPUB2's `<meta name="cover" content="<manifest-id>"/>` pointing
             at an image item (no properties="cover-image" support in EPUB2).
          3. Any image item whose id/filename looks like "cover" — some
             EPUB2 books skip the <meta> declaration too and just name the
             file itself (e.g. "cover.jpg").
        Returns (b"", "") if none of these find anything; the caller
        (ingestion.py) falls back to a title-generated cover in that case."""
        for item in book.get_items_of_type(ebooklib.ITEM_COVER):
            return item.get_content(), item.media_type

        cover_meta = book.get_metadata("OPF", "cover")
        if cover_meta:
            cover_id = cover_meta[0][1].get("content")
            if cover_id:
                item = book.get_item_with_id(cover_id)
                if item is not None:
                    return item.get_content(), item.media_type

        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            name = (item.get_id() + item.get_name()).lower()
            if "cover" in name:
                return item.get_content(), item.media_type

        return b"", ""

    @staticmethod
    def _meta(book: "epub.EpubBook", name: str) -> str:
        values = book.get_metadata("DC", name)
        return values[0][0] if values else ""

    @staticmethod
    def _toc_titles(book: "epub.EpubBook") -> dict[str, str]:
        """Flattens book.toc — a tree of epub.Link leaves and (Section,
        [children]) tuples for nested entries — into {href basename: title},
        keyed by _href_key so it matches spine items regardless of anchor
        fragments or absolute-vs-relative path differences between the TOC
        and the spine/manifest."""
        titles: dict[str, str] = {}

        def visit(entries) -> None:
            for entry in entries:
                if isinstance(entry, tuple):
                    section, children = entry
                    href = getattr(section, "href", None)
                    entry_title = getattr(section, "title", None)
                    if href and entry_title:
                        titles.setdefault(_href_key(href), entry_title.strip())
                    visit(children)
                else:
                    href = getattr(entry, "href", None)
                    entry_title = getattr(entry, "title", None)
                    if href and entry_title:
                        titles.setdefault(_href_key(href), entry_title.strip())

        visit(book.toc)
        return titles


def _href_key(href: str) -> str:
    return os.path.basename(href.split("#")[0])


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
