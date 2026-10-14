"""Compare retrieval modes for one query against the real vector store, side
by side — the fastest way to see why a chat answer cited the wrong passages.
Not part of the app; run from worker/src:

    cd worker/src
    python3 ../tests/search_smoke.py "整理关于小沛争夺的时间线"
    python3 ../tests/search_smoke.py "桃园结义" --book-id d033055c-4c99-4477-8936-24f363518819 --top-k 10
    python3 ../tests/search_smoke.py "辕门射戟" --mode bm25
    python3 ../tests/search_smoke.py "整理关于小沛争夺的时间线" --route

Runs the query through RetrievalPipeline.search once per mode (hybrid /
vector / bm25, or a single one via --mode) and prints fused score plus the
per-signal vector/keyword components. --route instead runs the two-stage
chapter-routed retrieval (search_by_chapter_route, the path the
search_by_chapters chat tool uses) and prints the routed chapters with their
aggregate scores and summaries before the re-ranked chunks. Things to look for:

- ids ending in ":summary" (flagged) — book/chapter summaries share the
  collection with real chunks, and their theme-word density makes them rank
  high on overview-ish questions, squeezing real passages out of the top-k.
- all-zero vector scores in every mode — the embedder call silently failed
  (RetrievalPipeline._vector_scores swallows the exception), so "hybrid"
  degraded to keyword-only with no warning. Happens e.g. when the local
  embedding model isn't downloaded and the machine can't reach HuggingFace.
- keyword hits with near-zero vector score that vanish in hybrid mode — the
  0.6 vector weight dilutes exact term matches ("小沛" losing to "争夺"
  near-misses was the case that motivated this script).

Same config trap as inspect_chapter_summary.py: sets $MYNEXUS_CONFIG_PATH to
the repo-root config.yaml when unset; --config overrides. Relative paths in
that config (./data/vectorstore, ./data/models) are relative to the Core API
process's cwd (the repo root), not to worker/src — this script rewrites them
against the repo root before building the pipeline.
"""

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_REPO_CONFIG_PATH = _REPO_ROOT / "config" / "config.yaml"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import load_config  # noqa: E402
from pipelines.retrieval import RetrievalPipeline  # noqa: E402


def _load_config(config_arg: str | None):
    if config_arg:
        os.environ["MYNEXUS_CONFIG_PATH"] = config_arg
    elif "MYNEXUS_CONFIG_PATH" not in os.environ:
        os.environ["MYNEXUS_CONFIG_PATH"] = str(_REPO_CONFIG_PATH)
    cfg = load_config()
    for attr in ("vector_store_path", "embedding_local_model_path"):
        value = getattr(cfg, attr, "")
        if value and not Path(value).is_absolute():
            setattr(cfg, attr, str((_REPO_ROOT / value).resolve()))
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query")
    parser.add_argument(
        "--book-id",
        action="append",
        dest="book_ids",
        default=None,
        help="restrict retrieval to this book (repeatable); default: whole library",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--mode", choices=["hybrid", "vector", "bm25"], default=None, help="default: all three")
    parser.add_argument("--route", action="store_true", help="two-stage chapter-routed retrieval instead of flat search")
    parser.add_argument("--config", default=None, help="path to config.yaml (default: repo-root config/config.yaml)")
    args = parser.parse_args()

    retrieval = RetrievalPipeline(_load_config(args.config))

    if args.route:
        chunks, chapters = retrieval.search_by_chapter_route(args.query, book_ids=args.book_ids, top_k=args.top_k)
        print(f"===== routed chapters ({len(chapters)}) =====")
        for i, c in enumerate(chapters, 1):
            print(f"[{i}] agg={c['score']:.3f} chapter={c['chapter_id'][:8]}")
            print(f"    summary: {c['summary'][:80]!r}")
        print(f"===== chunks within those chapters ({len(chunks)}) =====")
        for i, r in enumerate(chunks, 1):
            print(
                f"[{i}] fused={r['score']:.3f} vector={r['vector_score']:.3f} keyword={r['keyword_score']:.3f}"
                f" book={r['book_id'][:8]} chapter={r['chapter_id'][:8]}"
            )
            print(f"    {r['content'][:80]!r}")
        if not chunks:
            print("    (no hits — route found nothing; chat tool would fall back to semantic_search)")
        return

    modes = [args.mode] if args.mode else ["hybrid", "vector", "bm25"]

    for mode in modes:
        results = retrieval.search(args.query, book_ids=args.book_ids, top_k=args.top_k, mode=mode)
        print(f"===== mode={mode} ({len(results)} hits) =====")
        for i, r in enumerate(results, 1):
            flag = " [SUMMARY]" if r["id"].endswith(":summary") else ""
            print(
                f"[{i}] fused={r['score']:.3f} vector={r['vector_score']:.3f} keyword={r['keyword_score']:.3f}"
                f" book={r['book_id'][:8]} chapter={r['chapter_id'][:8]}{flag}"
            )
            print(f"    {r['content'][:80]!r}")
        if not results:
            print("    (no hits)")


if __name__ == "__main__":
    main()
