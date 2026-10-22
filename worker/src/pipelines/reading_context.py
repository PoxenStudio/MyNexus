import difflib
import logging
import re
import unicodedata

from grpc_client import CoreApiClient

logger = logging.getLogger(__name__)

_CHAPTER_PREFIX_RE = re.compile(
    r"^(第[0-9一二三四五六七八九十百千零〇两]+[章节回卷部篇]|chapter\s*\d+|ch\.?\s*\d+)"
    r"[\s:：.、,，\-—]*",
    re.IGNORECASE,
)
_CHAPTER_INTENT_RE = re.compile(
    r"(本章|这一章|当前章节|这章|本回|这一回|本章内容|本章.{0,6}(讲|内容|人物|情节|总结)|"
    r"总结.{0,6}(本章|这一章))"
)
_FULL_BOOK_RE = re.compile(r"(全书|整本|整部|这本书|本书|梗概|总览)")
_FUZZY_THRESHOLD = 0.65


def normalize_title(value: str) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value).lower()
    text = _CHAPTER_PREFIX_RE.sub("", text.strip())
    return re.sub(r"[\s\W_]+", "", text)


def _title_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.9
    return difflib.SequenceMatcher(None, left, right).ratio()


def _match_by_title(title: str, chapters: list[dict]) -> tuple[dict | None, str | None]:
    target = normalize_title(title)
    if not target:
        return None, None
    best: dict | None = None
    best_score = 0.0
    for chapter in chapters:
        score = _title_similarity(target, normalize_title(chapter.get("title", "")))
        if score > best_score:
            best, best_score = chapter, score
    if best is not None and best_score >= _FUZZY_THRESHOLD:
        method = "exact" if best_score == 1.0 else "fuzzy"
        return best, method
    return None, None


def _match_by_order(
    chapters: list[dict], section_index: int, progress_fraction: float
) -> tuple[dict | None, str | None]:
    ordered = sorted(chapters, key=lambda c: c.get("sort_order") or 0)
    if not ordered:
        return None, None
    if section_index > 0:
        for delta in (0, -1, 1):
            idx = section_index + delta
            if 0 <= idx < len(ordered):
                return ordered[idx], f"section_index{delta:+d}" if delta else "section_index"
    if 0.0 < progress_fraction <= 1.0:
        idx = round(progress_fraction * (len(ordered) - 1))
        idx = min(max(idx, 0), len(ordered) - 1)
        return ordered[idx], "fraction"
    return None, None


def _pick_book(infos: list[dict], reading: dict) -> dict | None:
    if not infos:
        return None
    if len(infos) == 1:
        return infos[0]
    target = normalize_title(reading.get("book_title", ""))
    if target:
        best, score = None, 0.0
        for info in infos:
            current = _title_similarity(target, normalize_title(info.get("title", "")))
            if current > score:
                best, score = info, current
        if best is not None and score >= _FUZZY_THRESHOLD:
            return best
    return infos[0]


def resolve_chapter(
    core_api: CoreApiClient, book_ids: list[str] | None, reading: dict
) -> dict | None:
    """把阅读位置映射到 Core API 的章节，失败返回 None 且不抛异常。"""
    if not reading or not book_ids:
        return None
    infos: list[dict] = []
    for book_id in book_ids:
        info = core_api.get_book_info_by_id(book_id)
        if info:
            infos.extend(info)
        if len(infos) > 1:
            break
    book = _pick_book(infos, reading)
    if book is None:
        logger.info("reading context unresolved: no book info for %s", book_ids)
        return None
    chapters = book.get("chapters") or []
    chapter, method = _match_by_title(reading.get("chapter_title", ""), chapters)
    if chapter is None:
        chapter, method = _match_by_order(
            chapters,
            int(reading.get("section_index") or 0),
            float(reading.get("progress_fraction") or 0.0),
        )
    if chapter is None:
        logger.info(
            "reading context unresolved: book=%s title=%r chapters=%d",
            book.get("book_id"), reading.get("chapter_title"), len(chapters),
        )
        return None
    resolved = {
        "book_id": book.get("book_id", ""),
        "book_title": book.get("title", ""),
        "chapter_id": chapter.get("chapter_id", ""),
        "title": chapter.get("title", ""),
        "sort_order": chapter.get("sort_order", 0),
        "method": method,
    }
    logger.info(
        "reading context resolved: book=%s chapter_id=%s title=%s method=%s",
        resolved["book_id"], resolved["chapter_id"], resolved["title"], method,
    )
    return resolved


def wants_chapter_summary(question: str) -> bool:
    if not question:
        return False
    if _FULL_BOOK_RE.search(question):
        return False
    return bool(_CHAPTER_INTENT_RE.search(question))


def _location_line(reading: dict) -> str:
    parts = []
    if reading.get("chapter_title"):
        parts.append(f"章节《{reading['chapter_title']}》")
    if reading.get("section_index"):
        parts.append(f"目录序号 {reading['section_index']}")
    fraction = reading.get("progress_fraction")
    if isinstance(fraction, (int, float)) and fraction > 0:
        parts.append(f"进度 {fraction * 100:.1f}%")
    if reading.get("page"):
        parts.append(f"约第 {reading['page']} 页")
    return "，".join(parts) or "位置未知"


def build_reading_section(reading: dict, selection: dict, chapter: dict | None) -> str:
    """构造 system prompt 中的阅读位置/选区片段，无数据时返回空串。"""
    if not reading and not selection:
        return ""
    lines = ["\n\n## 当前阅读位置"]
    if reading:
        if reading.get("book_title"):
            lines.append(f"- 书籍：《{reading['book_title']}》")
        chapter_title = reading.get("chapter_title") or (chapter or {}).get("title")
        if chapter_title:
            lines.append(f"- 当前章节：{chapter_title}")
        if chapter:
            lines.append(
                f"- 已定位章节：{chapter['title']}（目录序号 {chapter['sort_order']}，"
                f"chapter_id={chapter['chapter_id']}，匹配方式 {chapter['method']}）"
            )
        lines.append(f"- 阅读位置：{_location_line(reading)}")
        if reading.get("cfi"):
            lines.append(f"- 定位标识：{reading['cfi']}")
    if selection and selection.get("text"):
        lines.append("\n## 用户选中文本")
        lines.append(f"> {selection['text']}")
        selected_chapter = selection.get("chapter_title") or (chapter or {}).get("title") or ""
        selected_position = _location_line(selection)
        if selected_chapter:
            lines.append(f"选中位置：{selected_chapter}，{selected_position}")
        else:
            lines.append(f"选中位置：{selected_position}")
    lines.append(
        "\n阅读位置使用规则：\n"
        "1. 用户说“本章/这一章/当前章节/这里”时，指上述当前章节；说“这段/这句/选中的文字”时，指选中文本。\n"
        "2. 选中文本所在章节与当前章节不一致时，回答中分别说明来源，不要合并。\n"
        "3. 章节未能定位时，明确说明只能依据检索片段回答，不得假设章节内容。"
    )
    return "\n".join(lines)
