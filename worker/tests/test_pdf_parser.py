import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nodes.parsers.pdf_parser import PdfParser


class PdfParserTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.file_path = Path(self.temp_dir.name) / "research-paper.pdf"

    def _write_pdf(self, add_page_content):
        pdf = pymupdf.open()
        page = pdf.new_page(width=600, height=800)
        add_page_content(page)
        pdf.set_metadata({"title": "  ", "author": "Test Author"})
        pdf.save(self.file_path)
        pdf.close()

    def test_extracts_metadata_fallback_title_and_two_column_reading_order(self):
        def add_content(page):
            for y, text in zip((120, 160, 200, 240), ("LEFT ONE", "LEFT TWO", "LEFT THREE", "LEFT FOUR")):
                page.insert_text((72, y), text)
            for y, text in zip((120, 160, 200, 240), ("RIGHT ONE", "RIGHT TWO", "RIGHT THREE", "RIGHT FOUR")):
                page.insert_text((320, y), text)

        self._write_pdf(add_content)
        document = PdfParser().process(str(self.file_path))

        self.assertEqual(document.title, "research-paper")
        self.assertEqual(document.author, "Test Author")
        self.assertEqual(len(document.chapters), 1)
        content = document.chapters[0].content
        self.assertLess(content.index("LEFT FOUR"), content.index("RIGHT ONE"))
        self.assertLess(content.index("RIGHT ONE"), content.index("RIGHT FOUR"))

    def test_preserves_single_column_reading_order(self):
        def add_content(page):
            for y, text in zip((120, 160, 200), ("FIRST", "SECOND", "THIRD")):
                page.insert_text((72, y), text)

        self._write_pdf(add_content)
        content = PdfParser().process(str(self.file_path)).chapters[0].content

        self.assertLess(content.index("FIRST"), content.index("SECOND"))
        self.assertLess(content.index("SECOND"), content.index("THIRD"))

    def test_orders_three_columns_from_left_to_right(self):
        def add_content(page):
            for x, label in zip((72, 220, 368), ("LEFT", "MIDDLE", "RIGHT")):
                for y, number in zip((120, 160, 200, 240), range(1, 5)):
                    page.insert_text((x, y), f"{label} {number}")

        self._write_pdf(add_content)
        content = PdfParser().process(str(self.file_path)).chapters[0].content

        self.assertLess(content.index("LEFT 4"), content.index("MIDDLE 1"))
        self.assertLess(content.index("MIDDLE 4"), content.index("RIGHT 1"))

    def test_rejects_pdf_without_extractable_text(self):
        self._write_pdf(lambda _page: None)

        with self.assertRaisesRegex(ValueError, "scanned PDFs are not supported"):
            PdfParser().process(str(self.file_path))


if __name__ == "__main__":
    unittest.main()
