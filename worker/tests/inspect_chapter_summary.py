"""Standalone diagnostic for a single chapter's summary quality — reproduces
exactly what pipelines.summary.SummaryPipeline.run() does for one chapter
(same segment splitting, same prompt templates, same configured LLM
provider/model from config.yaml), without needing Core API, a task, or a
book already ingested into the app. Not part of the app; run from worker/src
(needs the same PYTHONPATH as the worker process):

    cd worker/src
    python3 ../tests/inspect_chapter_summary.py /path/to/book.epub

Lists every chapter with its length first (so you can sanity-check the split
itself — e.g. "chapter 1" turning out to be a cover/TOC/copyright page with
almost no real content explains a bad summary better than the LLM does),
then summarizes one chapter (--chapter, 0-indexed, default 0). A chapter
longer than util.text_split's hard limit gets split into multiple segments
(see split_into_segments) — this prints each segment's boundaries and prompt,
its own summary, then the final reduce prompt/summary that merges them, same
as a real run. Pass --show-content to also dump the chapter's full
parsed+cleaned text, useful for judging whether the parser/cleaner (not the
LLM) is where the quality loss actually happened.

Also prints the selected chapter's top-50 content keywords with their
weight/frequency — the same rolling per-segment extraction
pipelines.summary.SummaryPipeline._extract_chapter_keywords does for a real
run (jieba TF-IDF for Chinese, NLTK noun-POS term frequency for English; see
util/keywords.py), including the copyright/版权信息 title skip. This needs
no LLM call, so it prints even with --dry-run.

--debug writes the request/response to the OS temp dir the same way the
system settings "打开调试日志" toggle does in production (see
util/debug_log.py) — handy for diffing this run against a captured one from
a real task.

--base-url/--model/--api-key override config.yaml's llm.* section, e.g. to
compare the same chapter against a different model without touching the
running config.

Which config.yaml: config.load_config() reads $MYNEXUS_CONFIG_PATH, falling
back to the relative path "./config/config.yaml" if unset — which, run from
worker/src per above, resolves to worker/src/config/config.yaml (doesn't
exist), NOT the real repo-root config.yaml. Silently falling back to
load_config()'s built-in defaults (openai, empty api_key) then LGTMs the
parse/prompt-building steps and only blows up as a 401 once it actually
calls the LLM — confusing, since nothing about the file path or chapter
selection was wrong. So: if $MYNEXUS_CONFIG_PATH isn't already set, this
script points it at ../../config/config.yaml (the real one) before the first
load_config() call; pass --config to point at a different file instead.
"""

import argparse
import os
import sys
from pathlib import Path

_REPO_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "config.yaml"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import load_config  # noqa: E402
from pipelines.ingestion import IngestionPipeline  # noqa: E402

# Reaches into pipelines.summary's "private" (leading-underscore) module
# constants/templates rather than duplicating them here — the whole point of
# this script is to reproduce exactly what a real run would send, so
# importing them keeps this in sync automatically if the prompt/splitting
# logic ever changes instead of silently drifting from a copy-pasted version.
from pipelines.summary import (  # noqa: E402
    _CHAPTER_PROMPT_TEMPLATE,
    _CHAPTER_REDUCE_PROMPT_TEMPLATE,
    _KEYWORDS_PER_SEGMENT_TOP_K,
    _KEYWORDS_ROLLING_CAP,
    _SEGMENT_PROMPT_TEMPLATE,
    SummaryPipeline,
    _is_keyword_skip_chapter,
    _lang_bucket,
)
from util.keywords import extract_keywords, merge_topk  # noqa: E402
from util.text_split import DEFAULT_HARD_LIMIT_CHARS, split_into_segments  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file_path")
    parser.add_argument("--chapter", type=int, default=0, help="0-indexed chapter to summarize (default: 0)")
    parser.add_argument("--show-content", action="store_true", help="print the chapter's full parsed+cleaned text")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the chapter list + prompt(s) only, skip actual LLM calls"
    )
    parser.add_argument("--debug", action="store_true", help="also dump request/response via util/debug_log.py")
    parser.add_argument("--base-url", default=None, help="override config.yaml's llm.*.base_url")
    parser.add_argument("--model", default=None, help="override config.yaml's llm.*.model")
    parser.add_argument("--api-key", default=None, help="override config.yaml's llm.openai.api_key")
    parser.add_argument(
        "--config",
        default=None,
        help="path to config.yaml (default: $MYNEXUS_CONFIG_PATH, else the repo's real config/config.yaml)",
    )
    args = parser.parse_args()

    # See the module docstring's "Which config.yaml" section — without this,
    # load_config()'s relative default silently misses the real file when run
    # from worker/src as documented, and every llm.* value quietly falls back
    # to load_config()'s built-in defaults instead of erroring.
    if args.config:
        os.environ["MYNEXUS_CONFIG_PATH"] = args.config
    elif "MYNEXUS_CONFIG_PATH" not in os.environ:
        os.environ["MYNEXUS_CONFIG_PATH"] = str(_REPO_CONFIG_PATH)
    config_path = Path(os.environ["MYNEXUS_CONFIG_PATH"])
    if config_path.is_file():
        print(f"# reading config from {config_path}")
    else:
        print(f"# WARNING: {config_path} doesn't exist — load_config() will silently fall back to its")
        print("#   built-in defaults (openai, empty api_key), same as the 401 this script exists to explain.")
        print("#   Pass --config /path/to/config.yaml if the repo layout doesn't match what was guessed.")

    document = IngestionPipeline().parse_and_clean(args.file_path)
    if not document.chapters:
        print("# no chapters parsed out of this file — the split itself is the problem, not the LLM.")
        return

    print(f"# {document.title!r} by {document.author!r} — {len(document.chapters)} chapter(s)")
    for i, ch in enumerate(document.chapters):
        marker = ">" if i == args.chapter else " "
        n_segments = len(split_into_segments(ch.content))
        flag = f" [{n_segments} segments]" if n_segments > 1 else ""
        print(f"{marker} [{i}] {ch.title!r} — {len(ch.content)} chars{flag}")

    if not 0 <= args.chapter < len(document.chapters):
        print(f"\n# --chapter {args.chapter} out of range (0..{len(document.chapters) - 1})")
        return

    chapter = document.chapters[args.chapter]
    title = chapter.title or "（未命名章节）"
    print(f"\n# selected chapter [{args.chapter}]: {title!r}, {len(chapter.content)} chars")

    if args.show_content:
        print("\n----- parsed+cleaned content -----")
        print(chapter.content)
        print("----- end content -----")

    # Needs no LLM call — same rolling per-segment extraction a real run's
    # _extract_chapter_keywords does (see util/keywords.py), so this prints
    # even with --dry-run.
    lang = _lang_bucket(document.language)
    print(f"\n# language bucket: {lang!r} (books.language={document.language!r})")
    if _is_keyword_skip_chapter(chapter.title):
        print("# chapter title matches the copyright/版权信息 skip list — a real run excludes it from keywords entirely")
    else:
        keyword_totals: dict[str, float] = {}
        for seg in split_into_segments(chapter.content):
            candidates = extract_keywords(seg, lang, top_k=_KEYWORDS_PER_SEGMENT_TOP_K)
            keyword_totals = merge_topk(keyword_totals, candidates, _KEYWORDS_ROLLING_CAP)
        top50 = sorted(keyword_totals.items(), key=lambda kv: kv[1], reverse=True)[:50]
        print(f"\n----- top {len(top50)} keywords (of {len(keyword_totals)} after rolling merge) -----")
        for term, weight in top50:
            print(f"{term}\t{weight:.4f}")
        print("----- end keywords -----")

    cfg = load_config()
    if args.base_url:
        cfg.llm_openai.base_url = cfg.llm_ollama.base_url = args.base_url
    if args.model:
        cfg.llm_openai.model = cfg.llm_ollama.model = args.model
    if args.api_key:
        cfg.llm_openai.api_key = args.api_key
    cfg.debug_llm_logging = args.debug

    active = cfg.active_llm
    print(f"\n# provider={cfg.llm_provider} base_url={active.base_url} model={active.model}")

    segments = split_into_segments(chapter.content)
    if len(segments) <= 1:
        content = segments[0] if segments else ""
        prompt = _CHAPTER_PROMPT_TEMPLATE.format(title=title, content=content)
        print(f"\n# 1 segment ({len(content)} chars, under the {DEFAULT_HARD_LIMIT_CHARS}-char hard limit)")
        print("\n----- prompt sent to the LLM -----")
        print(prompt)
        print("----- end prompt -----")
    else:
        print(f"\n# {len(segments)} segments (chapter exceeds the {DEFAULT_HARD_LIMIT_CHARS}-char hard limit)")
        for i, seg in enumerate(segments):
            prompt = _SEGMENT_PROMPT_TEMPLATE.format(title=title, index=i + 1, total=len(segments), content=seg)
            print(f"\n----- segment [{i + 1}/{len(segments)}] prompt ({len(seg)} chars) -----")
            print(prompt)
        print(f"\n----- reduce prompt shape (filled in with each segment's summary once they exist) -----")
        print(
            _CHAPTER_REDUCE_PROMPT_TEMPLATE.format(
                title=title, total=len(segments), segment_summaries="<segment summaries go here>"
            )
        )

    if args.dry_run:
        print("\n# --dry-run: skipping the actual LLM call(s)")
        return

    pipeline = SummaryPipeline(cfg)
    summary = pipeline.summarize_chapter(chapter.title, chapter.content, on_progress=lambda msg: print(f"# {msg}"))
    print(f"\n----- summary ({len(summary)} chars) -----")
    print(summary)
    print("----- end summary -----")

    if args.debug:
        from util.debug_log import debug_dir

        print(f"\n# request/response files written under {debug_dir()}")


if __name__ == "__main__":
    main()
