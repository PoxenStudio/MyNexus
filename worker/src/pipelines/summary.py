import logging
import time
from typing import Callable

from config import WorkerConfig, load_config
from grpc_client import CoreApiClient
from nodes.factory import get_llm
from util.keywords import extract_keywords, merge_topk
from util.text_split import split_into_segments

logger = logging.getLogger(__name__)

# Keywords are extracted from each chapter's raw *content*, not its LLM-
# generated summary — a summary is short (~400 words) and paraphrased, which
# leaves too little of the book's actual vocabulary and too few term
# occurrences for TF-IDF/frequency stats to say much. Raw content has both,
# but a book's full text is too much to hold as one flat candidate pool, so
# extraction is done in a rolling reduce, two levels deep, mirroring the
# chapter-level map-reduce split_into_segments already does for LLM calls
# (reused here purely to bound each extract_keywords call's input size —
# jieba/NLTK have no LLM-style context-window limit, this is just about
# keeping each pass's working set small):
#   segment -> chapter: each segment's top _KEYWORDS_PER_SEGMENT_TOP_K
#     candidates are merged into a running per-chapter total.
#   chapter -> book: each chapter's running total is merged into a running
#     book-level total.
# Both levels are pruned back to _KEYWORDS_ROLLING_CAP after every merge
# (see util.keywords.merge_topk), so the in-memory term set never grows
# past a small multiple of that regardless of how many chapters/segments a
# book has — a term only survives by re-qualifying (i.e. actually being
# common enough to matter), not by being seen once and remembered forever.
_KEYWORDS_PER_SEGMENT_TOP_K = 50
# Comfortably above the default max_keywords system setting (50 — see
# config.KeywordConfig) so raising that setting still has real headroom to
# surface; Core API truncates further at read time regardless of what's
# stored here.
_KEYWORDS_ROLLING_CAP = 150

# Chapter titles skipped when building the book's keyword set — boilerplate
# like a copyright/imprint page contributes publisher/legal terms that have
# nothing to do with the book's actual content and would otherwise pollute
# the keyword cloud. Matched case-insensitively as a substring, not an exact
# title, so variants like "版权信息页" or "Copyright Page" / "Copyright ©
# 2020" are caught too. Only affects keyword extraction — the chapter is
# still summarized normally.
_KEYWORD_SKIP_TITLE_SUBSTRINGS = ("版权信息", "copyright")


def _is_keyword_skip_chapter(title: str) -> bool:
    title = (title or "").strip().lower()
    return any(s in title for s in _KEYWORD_SKIP_TITLE_SUBSTRINGS)


# Minimum gap between within-chapter progress ticks (see _complete's on_chars
# callback). A large chapter can take minutes to stream back from a slow
# model with nothing else to show for it in the meantime, so run() reports
# how many characters have been generated so far — but each tick is a gRPC
# call plus a stages_log append in Core API, so this is throttled by time
# (not by every delta) to keep that from growing unbounded on a long chapter.
_PROGRESS_TICK_SECONDS = 3.0

_CHAPTER_PROMPT_TEMPLATE = (
    "请用中文对下面的章节内容做摘要，控制在400字以内，只输出摘要正文本身，不要"
    "加“摘要：”之类的前缀，也不要复述章节标题。这是书籍章节摘要任务，不是对话，"
    "不要以“感谢你提供的详细信息”“您描述了”之类回应用户消息的语气开头，直接"
    "从摘要内容本身写起。\n\n"
    "章节标题：{title}\n\n正文：\n{content}"
)

# Used instead of _CHAPTER_PROMPT_TEMPLATE for one segment of a chapter too
# long for a single LLM call (see split_into_segments) — framed as "part N
# of M", not the whole chapter, so the model doesn't try to summarize things
# it hasn't seen yet or assume this segment is self-contained.
_SEGMENT_PROMPT_TEMPLATE = (
    "请用中文对下面的内容做摘要，控制在400字以内，只输出摘要正文本身，不要"
    "加“摘要：”之类的前缀。这段内容是《{title}》这一章节的第 {index}/{total} 部分"
    "（不是全章，只总结这部分实际出现的内容，不要补充你认为章节其他部分可能包含的内容）。"
    "这是书籍章节摘要任务，不是对话，不要以“感谢你提供的详细信息”“您描述了”之类"
    "回应用户消息的语气开头，直接从摘要内容本身写起。\n\n"
    "{content}"
)

# Reduce step for a multi-segment chapter: combines each segment's summary
# (from _SEGMENT_PROMPT_TEMPLATE) into one coherent chapter summary — the
# same shape as _BOOK_PROMPT_TEMPLATE's chapter-summaries-to-book-summary
# reduce, one level down.
_CHAPTER_REDUCE_PROMPT_TEMPLATE = (
    "下面是《{title}》这一章节按顺序分成 {total} 部分后，每部分的摘要。请把它们合并、"
    "改写成一段完整连贯的整章摘要，就像是通读全章后写的一样，不要出现“第一部分”这类"
    "分段措辞，控制在800字以内，只输出摘要正文本身。这是书籍章节摘要任务，不是对话，"
    "不要以“感谢你提供的详细信息”“您描述了”之类回应用户消息的语气开头，直接从摘要"
    "内容本身写起。\n\n{segment_summaries}"
)

_BOOK_PROMPT_TEMPLATE = (
    "下面是一本书中每一章的摘要，请综合这些内容，写一段对全书的整体总结，控制在"
    "1000字以内，覆盖全书的主要内容、脉络和核心观点，只输出总结正文本身。这是书籍"
    "整体摘要概括任务，不是对某段文字的摘要，你总结的对象是一本书的内容，不是一段文字。"
    "当前任务也不是对话，不要以“感谢你提供的详细信息”“您描述了”之类回应用户"
    "消息的语气开头，直接从摘要内容本身写起。\n\n"
    "{chapter_summaries}"
)

# English counterparts of the four templates above, used when the book's
# language (SummarizeRequest.language, from books.language — MyBooks-style
# 3-letter codes, see util/lang_detect.py) buckets to "en" (see
# _lang_bucket). Everything else (empty/"zho"/"zha"/"jpn"/any other code —
# e.g. "fra"/"deu" from a future MyBooks import, which this pipeline has no
# dedicated prompt set for) uses the Chinese templates unchanged — the
# project deliberately only maintains two prompt sets, see the design
# discussion this was built from.
_CHAPTER_PROMPT_TEMPLATE_EN = (
    "Summarize the following chapter in English, in no more than 400 words. "
    "Output only the summary text itself — no prefix like \"Summary:\", and "
    "don't just restate the chapter title. This is a book-chapter "
    "summarization task, not a conversation — don't open with a "
    "conversational reply like \"Thank you for providing the detailed "
    "information\" or \"You described...\"; start directly with the summary "
    "content itself.\n\n"
    "Chapter title: {title}\n\nContent:\n{content}"
)

_SEGMENT_PROMPT_TEMPLATE_EN = (
    "Summarize the following text in English, in no more than 400 words. "
    "Output only the summary text itself, no prefix like \"Summary:\". This is "
    "part {index}/{total} of the chapter \"{title}\" (not the whole chapter — "
    "only summarize what actually appears in this part, don't guess at what "
    "the rest of the chapter might contain). This is a book-chapter "
    "summarization task, not a conversation — don't open with a "
    "conversational reply like \"Thank you for providing the detailed "
    "information\" or \"You described...\"; start directly with the summary "
    "content itself.\n\n{content}"
)

_CHAPTER_REDUCE_PROMPT_TEMPLATE_EN = (
    "Below are the summaries of chapter \"{title}\", split into {total} parts in "
    "order. Merge and rewrite them into one coherent chapter summary, as if "
    "written after reading the whole chapter straight through — don't use "
    "phrasing like \"part one\". No more than 800 words, output only the "
    "summary text itself. This is a book-chapter summarization task, not a "
    "conversation — don't open with a conversational reply like \"Thank you "
    "for providing the detailed information\" or \"You described...\"; start "
    "directly with the summary content itself.\n\n{segment_summaries}"
)

_BOOK_PROMPT_TEMPLATE_EN = (
    "Below are the summaries of every chapter of a book. Synthesize them into "
    "one overall book summary in English, no more than 1000 words, covering "
    "the book's main content, structure and core ideas. Output only the "
    "summary text itself. This is a book summarization task, not a "
    "conversation — don't open with a conversational reply like \"Thank you "
    "for providing the detailed information\" or \"You described...\"; start "
    "directly with the summary content itself.\n\n{chapter_summaries}"
)


def _lang_bucket(language: str) -> str:
    """Buckets books.language (MyBooks-style 3-letter code, e.g. "eng"/
    "zho"/"zha"/"jpn" — see util/lang_detect.py) down to the two prompt/
    keyword-extraction paths this pipeline actually maintains: "en" for
    English ("eng"), "zh" for everything else — Traditional Chinese and
    Japanese books are summarized in Chinese too, by design, and any other
    code this pipeline has no dedicated prompt set for falls back to
    Chinese rather than erroring."""
    return "en" if (language or "").strip().lower() == "eng" else "zh"


class SummaryPipeline:
    """Two nested levels of map-reduce.

    Book level: each chapter is summarized individually and persisted
    immediately (via report_chapter_summary) as soon as it's done, so a
    crash partway through a long book doesn't lose the chapters already
    summarized. Once every chapter has a summary, they're combined into one
    whole-book summary (report_book_summary), which also marks the task
    complete.

    Chapter level (summarize_chapter): a chapter too long for one LLM call
    is itself map-reduced instead of truncated — split_into_segments cuts it
    at paragraph/sentence boundaries, each segment gets its own summary, and
    those get merged into one chapter summary. Most chapters fit in a single
    segment and this collapses to one LLM call, same as before this existed
    (see docs/Todos.md for why plain truncation wasn't good enough).

    Reuses whichever LLM provider is configured for chat (`llm.provider` in
    config.yaml) — there's no separate summarization-model setting, see
    docs/部署说明.md.
    """

    def __init__(self, config: WorkerConfig | None = None) -> None:
        self.config = config or load_config()
        self.llm = get_llm(self.config)
        self.core_api = CoreApiClient(self.config)

    def _complete(self, prompt: str, on_chars: Callable[[int], None] | None = None) -> str:
        # llm.process() streams deltas (it's built for the interactive chat
        # case); a batch job like this just wants the final text — but for a
        # slow/large call, on_chars (if given) still gets a callback with the
        # running character count every _PROGRESS_TICK_SECONDS, so the caller
        # can surface "still working" progress instead of going silent until
        # the whole completion lands.
        chunks: list[str] = []
        last_tick = time.monotonic()
        for delta in self.llm.process([{"role": "user", "content": prompt}]):
            chunks.append(delta)
            if on_chars is not None:
                now = time.monotonic()
                if now - last_tick >= _PROGRESS_TICK_SECONDS:
                    on_chars(sum(len(c) for c in chunks))
                    last_tick = now
        return "".join(chunks).strip()

    def summarize_chapter(
        self, title: str, content: str, lang: str = "zh", on_progress: Callable[[str], None] | None = None
    ) -> str:
        """on_progress (if given) is called with a short human-readable
        status string — "生成中…已输出 N 字" for a single-segment chapter,
        "第 i/total 段，已输出 N 字" then "正在合并 total 段摘要…" for a
        multi-segment one — every _PROGRESS_TICK_SECONDS (see _complete).
        Wraps _complete's lower-level char-count callback rather than
        exposing it directly, since what counts as meaningful progress
        differs between the two cases.

        lang: "en" or "zh" (see _lang_bucket) — selects which prompt
        language the summary itself is written in; the progress messages
        stay Chinese either way since they're UI-facing status text, not
        part of the generated summary."""
        title = title or "（未命名章节）"
        segments = split_into_segments(content)
        if not segments:
            return ""

        chapter_tmpl = _CHAPTER_PROMPT_TEMPLATE_EN if lang == "en" else _CHAPTER_PROMPT_TEMPLATE
        segment_tmpl = _SEGMENT_PROMPT_TEMPLATE_EN if lang == "en" else _SEGMENT_PROMPT_TEMPLATE
        reduce_tmpl = _CHAPTER_REDUCE_PROMPT_TEMPLATE_EN if lang == "en" else _CHAPTER_REDUCE_PROMPT_TEMPLATE

        if len(segments) == 1:
            prompt = chapter_tmpl.format(title=title, content=segments[0])
            on_chars = (lambda chars: on_progress(f"生成中…已输出 {chars} 字")) if on_progress else None
            return self._complete(prompt, on_chars=on_chars)

        # Map: summarize each segment on its own.
        segment_summaries = []
        for i, segment in enumerate(segments):
            prompt = segment_tmpl.format(title=title, index=i + 1, total=len(segments), content=segment)
            on_chars = (
                (lambda chars, i=i, total=len(segments): on_progress(f"第 {i + 1}/{total} 段，已输出 {chars} 字"))
                if on_progress
                else None
            )
            segment_summaries.append(self._complete(prompt, on_chars=on_chars))

        # Reduce: merge the segment summaries into one chapter summary.
        if on_progress:
            on_progress(f"正在合并 {len(segments)} 段摘要…")
        reduce_prompt = reduce_tmpl.format(
            title=title,
            total=len(segments),
            segment_summaries="\n\n".join(f"[{i + 1}/{len(segments)}] {s}" for i, s in enumerate(segment_summaries)),
        )
        return self._complete(reduce_prompt)

    def summarize_book(self, chapter_summaries: list[tuple[str, str]], lang: str = "zh") -> str:
        joined = "\n\n".join(
            f"[{i + 1}] {title or '（未命名章节）'}\n{summary}" for i, (title, summary) in enumerate(chapter_summaries)
        )
        prompt = (_BOOK_PROMPT_TEMPLATE_EN if lang == "en" else _BOOK_PROMPT_TEMPLATE).format(chapter_summaries=joined)
        return self._complete(prompt)

    def _extract_chapter_keywords(self, content: str, lang: str) -> dict[str, float]:
        """Rolling top-K keyword extraction across one chapter's segments —
        see the module-level comment above _KEYWORDS_PER_SEGMENT_TOP_K for
        why this runs on split_into_segments pieces and why it's a rolling
        merge rather than one extract_keywords call over the whole chapter."""
        totals: dict[str, float] = {}
        for segment in split_into_segments(content):
            candidates = extract_keywords(segment, lang, top_k=_KEYWORDS_PER_SEGMENT_TOP_K)
            totals = merge_topk(totals, candidates, _KEYWORDS_ROLLING_CAP)
        return totals

    def run(
        self, task_id: str, book_id: str, chapters: list, force_restart: bool = True, language: str = ""
    ) -> None:
        """chapters: protobuf Chapter messages (id/title/content/summary —
        see mynexus.proto's SummarizeRequest). Never raises: failures are
        reported via report_fail instead, mirroring ingestion.py's run(),
        since this runs inside a background thread with no caller to catch
        it (see server.py's TriggerSummarize).

        force_restart=False ("continue") skips chapters that already carry
        a non-empty `summary` and reuses it as-is for the reduce step —
        used to resume a partial run (e.g. after a retry) without paying
        to redo chapters that already succeeded. force_restart=True
        ("restart") regenerates every chapter regardless.

        language: books.language (see util/lang_detect.py) — bucketed via
        _lang_bucket to pick the prompt language and keyword-extraction path.
        """
        try:
            lang = _lang_bucket(language)
            usable = [ch for ch in chapters if ch.content.strip()]
            if not usable:
                raise ValueError("book has no chapter content to summarize")

            to_generate = usable if force_restart else [ch for ch in usable if not ch.summary.strip()]

            self.core_api.report_progress(task_id, 5, "summarizing_chapters")

            # Keeps original chapter order for the reduce step: chapters not
            # in to_generate keep their existing summary untouched.
            summaries_by_id = {ch.id: ch.summary for ch in usable}
            total = len(to_generate)
            for i, ch in enumerate(to_generate):
                # Progress before this chapter starts — the same value
                # chapter i-1's completion reported (or the initial 5%),
                # so within-chapter ticks below don't move the percentage,
                # only the message.
                chapter_progress = 5 + int(80 * i / max(total, 1))
                chapter_label = f"{i + 1}/{total} 《{ch.title or '未命名章节'}》"

                def on_progress(message: str, label: str = chapter_label, progress: int = chapter_progress) -> None:
                    self.core_api.report_progress(task_id, progress, "summarizing_chapters", f"{label} {message}")

                summary = self.summarize_chapter(ch.title, ch.content, lang=lang, on_progress=on_progress)
                self.core_api.report_chapter_summary(task_id, ch.id, summary)
                summaries_by_id[ch.id] = summary
                # Map phase is 5..85%; reduce covers the remaining stretch to 100%.
                progress = 5 + int(80 * (i + 1) / max(total, 1))
                self.core_api.report_progress(task_id, progress, "chapter_summarized", f"{i + 1}/{total}")

            chapter_summaries = [(ch.title, summaries_by_id[ch.id]) for ch in usable]
            book_summary = self.summarize_book(chapter_summaries, lang=lang)

            # Keywords are extracted from every usable chapter's raw
            # *content* (not the LLM summary — see the comment above
            # _KEYWORDS_PER_SEGMENT_TOP_K), independent of which chapters
            # were actually (re)generated this run, so a "continue" run
            # against a book that already had chapter summaries always ends
            # up with a complete book-level keyword set, not just coverage
            # of whatever chapters happened to be regenerated. Rolling
            # reduce at the book level mirrors _extract_chapter_keywords'
            # segment-level one, for the same memory-bounding reason.
            keyword_totals: dict[str, float] = {}
            for ch in usable:
                if _is_keyword_skip_chapter(ch.title):
                    continue
                chapter_keywords = self._extract_chapter_keywords(ch.content, lang)
                keyword_totals = merge_topk(keyword_totals, list(chapter_keywords.items()), _KEYWORDS_ROLLING_CAP)
            keywords = sorted(keyword_totals.items(), key=lambda item: item[1], reverse=True)

            self.core_api.report_progress(task_id, 95, "reducing_done")
            self.core_api.report_book_summary(task_id, book_id, book_summary, keywords)
        except Exception as exc:  # noqa: BLE001
            logger.exception("summarization failed (task_id=%s book_id=%s)", task_id, book_id)
            self.core_api.report_fail(task_id, str(exc))


if __name__ == "__main__":
    # Standalone dry-run, no Core API/gRPC involved:
    #   python3 -m pipelines.summary path/to/book.epub
    import argparse

    from pipelines.ingestion import IngestionPipeline

    parser = argparse.ArgumentParser(description="Dry-run chapter + book summarization on a local file.")
    parser.add_argument("file_path")
    args = parser.parse_args()

    doc = IngestionPipeline().parse_and_clean(args.file_path)
    lang = _lang_bucket(doc.language)
    pipeline = SummaryPipeline()
    summaries = []
    for chapter in doc.chapters:
        s = pipeline.summarize_chapter(chapter.title, chapter.content, lang=lang)
        print(f"[{chapter.title}]\n{s}\n")
        summaries.append((chapter.title, s))
    print("=== BOOK SUMMARY ===")
    print(pipeline.summarize_book(summaries, lang=lang))
    print("=== KEYWORDS ===")
    totals: dict[str, float] = {}
    for chapter in doc.chapters:
        if _is_keyword_skip_chapter(chapter.title):
            continue
        chapter_keywords = pipeline._extract_chapter_keywords(chapter.content, lang)  # noqa: SLF001
        totals = merge_topk(totals, list(chapter_keywords.items()), _KEYWORDS_ROLLING_CAP)
    for term, weight in sorted(totals.items(), key=lambda item: item[1], reverse=True):
        print(f"{term}\t{weight:.3f}")
