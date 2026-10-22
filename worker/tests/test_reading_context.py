import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pipelines import reading_context


class FakeCoreApi:
    def __init__(self, books: dict, located: dict | None = None):
        self.books = books
        self.located = located or {}
        self.calls: list[str] = []
        self.locate_calls: list[tuple[str, str]] = []

    def get_book_info_by_id(self, book_id: str):
        self.calls.append(book_id)
        return self.books.get(book_id)

    def locate_chapter_by_text(self, book_id: str, text: str):
        self.locate_calls.append((book_id, text))
        return self.located.get(text)


def book(book_id="b1", title="长安十二时辰", chapters=None):
    return [
        {
            "book_id": book_id,
            "title": title,
            "chapters": chapters
            if chapters is not None
            else [
                {"chapter_id": "c1", "title": "第一章 巳初", "sort_order": 1},
                {"chapter_id": "c2", "title": "第二章 午初", "sort_order": 2},
                {"chapter_id": "c3", "title": "第三章 巳正", "sort_order": 3},
            ],
        }
    ]


class ResolveChapterTests(unittest.TestCase):
    def test_exact_title_word_suffix_match(self):
        api = FakeCoreApi({"b1": book()})
        resolved = reading_context.resolve_chapter(
            api, ["b1"], {"book_title": "长安十二时辰", "chapter_title": "第三章 巳正"}
        )
        self.assertEqual(resolved["chapter_id"], "c3")
        self.assertEqual(resolved["method"], "exact")

    def test_title_without_chapter_prefix_matches(self):
        api = FakeCoreApi({"b1": book()})
        resolved = reading_context.resolve_chapter(api, ["b1"], {"chapter_title": "巳正"})
        self.assertEqual(resolved["chapter_id"], "c3")
        self.assertEqual(resolved["method"], "exact")

    def test_snippet_locates_chapter_when_title_unknown(self):
        api = FakeCoreApi(
            {"b1": book()},
            located={"他在辰时进入长安城": {"chapter_id": "c1", "title": "第一章 巳初", "sort_order": 1}},
        )
        resolved = reading_context.resolve_chapter(
            api,
            ["b1"],
            {"chapter_title": "不存在的标题", "section_index": 1, "snippet": "他在辰时进入长安城"},
        )
        self.assertEqual(resolved["chapter_id"], "c1")
        self.assertEqual(resolved["method"], "snippet")

    def test_snippet_miss_still_falls_back_to_section_index(self):
        api = FakeCoreApi({"b1": book()})
        resolved = reading_context.resolve_chapter(
            api,
            ["b1"],
            {"chapter_title": "不存在的标题", "section_index": 1, "snippet": "完全无关的文字"},
        )
        self.assertEqual(resolved["chapter_id"], "c2")
        self.assertEqual(resolved["method"], "section_index")

    def test_unknown_title_falls_back_to_section_index(self):
        api = FakeCoreApi({"b1": book()})
        resolved = reading_context.resolve_chapter(
            api, ["b1"], {"chapter_title": "不存在的标题", "section_index": 1}
        )
        self.assertEqual(resolved["chapter_id"], "c2")
        self.assertEqual(resolved["method"], "section_index")

    def test_section_index_off_by_one_is_recovered(self):
        api = FakeCoreApi({"b1": book()})
        resolved = reading_context.resolve_chapter(
            api, ["b1"], {"chapter_title": "不存在的标题", "section_index": 3}
        )
        self.assertEqual(resolved["chapter_id"], "c3")
        self.assertEqual(resolved["method"], "section_index-1")

    def test_out_of_range_section_index_returns_none(self):
        api = FakeCoreApi({"b1": book()})
        self.assertIsNone(
            reading_context.resolve_chapter(
                api, ["b1"], {"chapter_title": "不存在的标题", "section_index": 99}
            )
        )

    def test_fraction_fallback_without_section_index(self):
        api = FakeCoreApi({"b1": book()})
        resolved = reading_context.resolve_chapter(
            api, ["b1"], {"chapter_title": "不存在的标题", "progress_fraction": 0.5}
        )
        self.assertEqual(resolved["chapter_id"], "c2")
        self.assertEqual(resolved["method"], "fraction")

    def test_no_book_info_returns_none(self):
        api = FakeCoreApi({})
        self.assertIsNone(
            reading_context.resolve_chapter(api, ["b1"], {"chapter_title": "第三章 巳正"})
        )

    def test_empty_reading_skips_rpc(self):
        api = FakeCoreApi({"b1": book()})
        self.assertIsNone(reading_context.resolve_chapter(api, ["b1"], {}))
        self.assertEqual(api.calls, [])

    def test_multi_book_scope_picks_matching_title(self):
        api = FakeCoreApi(
            {"b1": book("b1", "另一本书"), "b2": book("b2", "长安十二时辰")}
        )
        resolved = reading_context.resolve_chapter(
            api, ["b1", "b2"], {"book_title": "长安十二时辰", "chapter_title": "第二章 午初"}
        )
        self.assertEqual(resolved["book_id"], "b2")
        self.assertEqual(resolved["chapter_id"], "c2")


class ChapterIntentTests(unittest.TestCase):
    def test_chapter_summary_intents(self):
        for text in ("本章讲了什么", "这一章的主要内容", "总结一下当前章节", "这一回讲了什么"):
            self.assertTrue(reading_context.wants_chapter_summary(text), text)

    def test_full_book_intents_are_not_chapter_scoped(self):
        for text in ("这本书讲了什么", "全书的梗概", "整本书的结构", "本章在全书中起什么作用"):
            self.assertFalse(reading_context.wants_chapter_summary(text), text)

    def test_unrelated_question(self):
        self.assertFalse(reading_context.wants_chapter_summary("谁是主角"))


class ReadingSectionTests(unittest.TestCase):
    def test_empty_context_produces_empty_section(self):
        self.assertEqual(reading_context.build_reading_section({}, {}, None), "")

    def test_section_contains_location_selection_and_rules(self):
        chapter = {
            "chapter_id": "c3",
            "title": "第三章 巳正",
            "book_id": "b1",
            "sort_order": 3,
            "method": "exact",
        }
        reading = {
            "book_title": "长安十二时辰",
            "chapter_title": "第三章 巳正",
            "section_index": 12,
            "progress_fraction": 0.42,
            "page": 118,
            "cfi": "epubcfi(/6/26!/4/2/2[c03])",
        }
        selection = {"text": "长安一片月", "chapter_title": "第三章 巳正", "page": 118}
        section = reading_context.build_reading_section(reading, selection, chapter)
        self.assertIn("长安十二时辰", section)
        self.assertIn("chapter_id=c3", section)
        self.assertIn("42.0%", section)
        self.assertIn("长安一片月", section)
        self.assertIn("选中文本所在章节与当前章节不一致", section)

    def test_section_without_resolved_chapter(self):
        section = reading_context.build_reading_section(
            {"chapter_title": "第三章 巳正"}, {}, None
        )
        self.assertIn("当前章节：第三章 巳正", section)
        self.assertNotIn("已定位章节", section)


if __name__ == "__main__":
    unittest.main()
