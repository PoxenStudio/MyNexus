import logging
import re

import jieba

logger = logging.getLogger(__name__)

jieba.setLogLevel(logging.WARNING)

# Functional / question words that must never become search terms. Kept small
# and specific: term candidates are additionally confirmed verbatim against
# chapter full text, so a borderline token that actually appears in a chapter
# can still survive via the bigram pass.
_STOPWORDS = {
    "什么", "怎么", "怎样", "哪里", "哪儿", "哪个", "哪些", "谁", "为何", "为什么",
    "如何", "请问", "可以", "能够", "一下", "我们", "他们", "她们", "它们",
    "这个", "那个", "这些", "那些", "这样", "那样", "这里", "那里", "其中",
    "主要", "关于", "对于", "根据", "以及", "还是", "或者", "但是", "因为",
    "所以", "如果", "虽然", "然后", "现在", "已经", "没有", "不是", "一个",
    "书中", "书里", "本文", "本章", "本章", "章节", "内容", "问题", "回答",
    "意思", "是什么", "是指", "指的是", "有什么", "有哪些", "怎么样",
    "中", "的", "了", "是", "在", "和", "与", "或", "及", "之", "其",
}

# Strip 《book》 markers for term extraction — the title is used for chapter
# candidate routing via chunk search, not as an in-text term.
_BOOK_TITLE_RE = re.compile(r"《[^》]{1,60}》")
_CJK_RUN_RE = re.compile(r"[一-鿿]{2,}")
_TOKEN_VALID_RE = re.compile(r"[一-鿿a-zA-Z]")


def extract_terms(question: str, max_terms: int = 8) -> list[str]:
    """Salient lookup terms for a question: jieba words (len>=2) plus adjacent
    CJK bigrams. Bigrams are mandatory because rare/ancient proper nouns
    (合淝、樊城、逍逍津) are OOV for jieba and get split into single chars.
    Final confirmation happens against real chapter text in confirm()."""
    stripped = _BOOK_TITLE_RE.sub(" ", question)
    terms: list[str] = []
    seen: set[str] = set()

    def add(t: str) -> None:
        t = t.strip().lower()
        if len(t) < 2 or t in _STOPWORDS or t in seen:
            return
        if not _TOKEN_VALID_RE.search(t):
            return
        seen.add(t)
        terms.append(t)

    for tok in jieba.lcut(stripped):
        add(tok)

    for run in _CJK_RUN_RE.findall(stripped):
        chars = [c for c in run if c not in "的了是在和与之其"]
        for i in range(len(chars) - 1):
            add(chars[i] + chars[i + 1])

    return terms[:max_terms]


def _merge_windows(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not windows:
        return []
    windows.sort()
    merged = [windows[0]]
    for start, end in windows[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _snippet(text: str, start: int, end: int) -> str:
    snippet = text[start:end].strip()
    snippet = re.sub(r"\s+", " ", snippet)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def confirm_in_chapters(
    core_api,
    question: str,
    candidate_chapters: list[dict],
    max_chapters: int = 3,
    max_candidates: int = 8,
    min_content_chars: int = 200,
    window_chars: int = 160,
    total_budget: int = 5000,
) -> list[dict]:
    """Full-text confirmation over complete chapter plain text (mirrors
    ReadAny's fallbackSearch): take candidate chapters produced by chunk
    retrieval, fetch their full content via core-api, locate every verbatim
    occurrence of the question's salient terms, and return surrounding
    snippets (one entry each, with book_id/chapter_id/title) so the caller
    can align context numbering with its citations array 1:1.

    candidate_chapters: [{book_id, chapter_id, title?}] in priority order.
    Empty results mean no exact term hit was confirmed in full text —
    caller keeps chunk-only context.
    """
    terms = extract_terms(question)
    if not terms or not candidate_chapters:
        return []

    snippets: list[dict] = []
    spent = 0
    used_chapters = 0
    scanned = 0

    for ch in candidate_chapters:
        if used_chapters >= max_chapters or spent >= total_budget:
            break
        if scanned >= max_candidates:
            break
        scanned += 1
        chapter = core_api.get_chapter_content(ch["book_id"], ch["chapter_id"])
        if not chapter:
            logger.warning("fulltext: chapter fetch failed b=%s c=%s", ch["book_id"], ch["chapter_id"])
            continue
        full = chapter["content"]
        if len(full) < min_content_chars:
            logger.info("fulltext: skip near-empty chapter %s(%d chars)", chapter["title"], len(full))
            continue
        low = full.lower()

        windows: list[tuple[int, int]] = []
        hit_terms: set[str] = set()
        for term in terms:
            pos = low.find(term)
            while pos != -1:
                hit_terms.add(term)
                windows.append((max(0, pos - window_chars), min(len(full), pos + len(term) + window_chars)))
                pos = low.find(term, pos + len(term))

        if not windows:
            continue

        merged = _merge_windows(windows)
        added = 0
        for start, end in merged:
            text = _snippet(full, start, end)
            if spent + len(text) > total_budget:
                break
            # One entry per snippet so callers can align context [n] numbering
            # 1:1 with the emitted citations array.
            snippets.append(
                {
                    "book_id": ch["book_id"],
                    "chapter_id": chapter["chapter_id"],
                    "title": chapter["title"],
                    "text": text,
                    "terms": sorted(hit_terms),
                }
            )
            spent += len(text)
            added += 1

        if added:
            logger.info(
                "fulltext confirmed: chapter=%s(%s) terms=%s windows=%d kept=%d",
                chapter["title"], chapter["chapter_id"][:8], sorted(hit_terms), len(merged), added,
            )
            used_chapters += 1

    return snippets
