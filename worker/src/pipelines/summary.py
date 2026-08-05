import logging

from config import WorkerConfig, load_config
from grpc_client import CoreApiClient
from nodes.factory import get_llm

logger = logging.getLogger(__name__)

_CHAPTER_PROMPT_TEMPLATE = (
    "请用中文对下面的章节内容做摘要，控制在200字以内，只输出摘要正文本身，不要"
    "加“摘要：”之类的前缀，也不要复述章节标题。\n\n"
    "章节标题：{title}\n\n正文：\n{content}"
)

_BOOK_PROMPT_TEMPLATE = (
    "下面是一本书每一章的摘要，请综合这些内容，写一段全书的整体总结，控制在"
    "500字以内，覆盖全书的主要内容、脉络和核心观点，只输出总结正文本身。\n\n"
    "{chapter_summaries}"
)

# Chapters longer than this are truncated before being sent to the LLM, so a
# single unusually long chapter can't fail the whole run against a
# smaller-context model. A proper sub-chapter map-reduce pass (summarize
# chunks of the chapter, then reduce those) would avoid the truncation
# entirely but adds a lot of complexity — worth revisiting if this turns out
# to be too lossy in practice.
_MAX_CHAPTER_CHARS = 12000


class SummaryPipeline:
    """Map-reduce whole-book summarization.

    Map: each chapter is summarized individually and persisted immediately
    (via report_chapter_summary) as soon as it's done, so a crash partway
    through a long book doesn't lose the chapters already summarized.
    Reduce: once every chapter has a summary, they're combined into one
    whole-book summary (report_book_summary), which also marks the task
    complete.

    Reuses whichever LLM provider is configured for chat (`llm.provider` in
    config.yaml) — there's no separate summarization-model setting, see
    docs/部署说明.md.
    """

    def __init__(self, config: WorkerConfig | None = None) -> None:
        self.config = config or load_config()
        self.llm = get_llm(self.config)
        self.core_api = CoreApiClient(self.config)

    def _complete(self, prompt: str) -> str:
        # llm.process() streams deltas (it's built for the interactive chat
        # case); a batch job like this just wants the final text.
        return "".join(self.llm.process([{"role": "user", "content": prompt}])).strip()

    def summarize_chapter(self, title: str, content: str) -> str:
        prompt = _CHAPTER_PROMPT_TEMPLATE.format(
            title=title or "（未命名章节）", content=content[:_MAX_CHAPTER_CHARS]
        )
        return self._complete(prompt)

    def summarize_book(self, chapter_summaries: list[tuple[str, str]]) -> str:
        joined = "\n\n".join(
            f"[{i + 1}] {title or '（未命名章节）'}\n{summary}" for i, (title, summary) in enumerate(chapter_summaries)
        )
        prompt = _BOOK_PROMPT_TEMPLATE.format(chapter_summaries=joined)
        return self._complete(prompt)

    def run(self, task_id: str, book_id: str, chapters: list) -> None:
        """chapters: protobuf Chapter messages (id/title/content — see
        mynexus.proto's SummarizeRequest). Never raises: failures are
        reported via report_fail instead, mirroring ingestion.py's run(),
        since this runs inside a background thread with no caller to catch
        it (see server.py's TriggerSummarize)."""
        try:
            usable = [ch for ch in chapters if ch.content.strip()]
            if not usable:
                raise ValueError("book has no chapter content to summarize")

            self.core_api.report_progress(task_id, 5, "summarizing_chapters")

            chapter_summaries: list[tuple[str, str]] = []
            total = len(usable)
            for i, ch in enumerate(usable):
                summary = self.summarize_chapter(ch.title, ch.content)
                self.core_api.report_chapter_summary(task_id, ch.id, summary)
                chapter_summaries.append((ch.title, summary))
                # Map phase is 5..85%; reduce covers the remaining stretch to 100%.
                progress = 5 + int(80 * (i + 1) / total)
                self.core_api.report_progress(task_id, progress, "chapter_summarized", f"{i + 1}/{total}")

            book_summary = self.summarize_book(chapter_summaries)
            self.core_api.report_progress(task_id, 95, "reducing_done")
            self.core_api.report_book_summary(task_id, book_id, book_summary)
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
    pipeline = SummaryPipeline()
    summaries = []
    for chapter in doc.chapters:
        s = pipeline.summarize_chapter(chapter.title, chapter.content)
        print(f"[{chapter.title}]\n{s}\n")
        summaries.append((chapter.title, s))
    print("=== BOOK SUMMARY ===")
    print(pipeline.summarize_book(summaries))
