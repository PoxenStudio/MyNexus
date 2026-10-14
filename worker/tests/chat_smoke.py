"""Manually run one chat question through the full QA pipeline (tool-decision
loop + retrieval + streamed answer) against the real config/vector store, and
print every stage that matters when an answer comes back wrong. Not part of
the app; run from worker/src:

    cd worker/src
    python3 ../tests/chat_smoke.py "请总结《三国演义》中小沛争夺的时间线"
    python3 ../tests/chat_smoke.py "这本书讲了什么" --book-id d033055c-4c99-4477-8936-24f363518819 --top-k 10

Output, in order:
- [decide] one line per tool-decision round: which tool the model picked with
  what arguments, or that it chose the plain-RAG path. Silence here plus an
  immediate "no tool chosen" on a question that obviously needs one means the
  decision call itself failed — see QAPipeline._decide_tool's bare except.
- [tool] one line per tool run: result size, or the error returned to the LLM.
- the streamed answer text.
- the final citations with fused score and book/chapter ids; ids ending in
  ":summary" are flagged — book/chapter summaries share the retrieval pool
  with real chunks and their theme-word density makes them outrank relevant
  passages on overview-ish questions.

Exit code 0 when the answer is non-empty, 1 otherwise. The useful signal for
"答非所问" regressions is upstream of the answer text (decision path +
citations), which is why those print first.

Core API (localhost:9090) is only needed when the model actually picks a
tool — the plain-RAG path never touches CoreApiClient (grpc channels connect
lazily). Config resolution is the same trap documented in
inspect_chapter_summary.py: this script points $MYNEXUS_CONFIG_PATH at the
repo-root config.yaml when unset; pass --config to override. Relative paths
in that config (./data/vectorstore, ./data/models) are relative to the Core
API process's cwd (the repo root), not to worker/src — this script rewrites
them against the repo root before building the pipeline.
"""

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_REPO_CONFIG_PATH = _REPO_ROOT / "config" / "config.yaml"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import load_config  # noqa: E402
from pipelines.qa import QAPipeline  # noqa: E402


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
    parser.add_argument("question")
    parser.add_argument(
        "--book-id",
        action="append",
        dest="book_ids",
        default=None,
        help="restrict retrieval to this book (repeatable); default: whole library",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--config", default=None, help="path to config.yaml (default: repo-root config/config.yaml)")
    args = parser.parse_args()

    qa = QAPipeline(_load_config(args.config))

    orig_decide = qa._decide_tool

    def spy_decide(messages):
        result = orig_decide(messages)
        if result is None:
            print("[decide] no tool chosen -> plain RAG path", flush=True)
        else:
            print(f"[decide] tool={result[0]} args={json.dumps(result[1], ensure_ascii=False)}", flush=True)
        return result

    qa._decide_tool = spy_decide

    orig_run = qa.tools.run

    def spy_run(name, arguments):
        result = orig_run(name, arguments)
        err = result.get("error")
        size = len(json.dumps(result, ensure_ascii=False))
        print(f"[tool] {name} -> {'ERROR: ' + err if err else f'{size} chars'}", flush=True)
        return result

    qa.tools.run = spy_run

    messages = [{"role": "user", "content": args.question}]
    answer_chars = 0
    citations: list[dict] = []
    print("--- answer ---", flush=True)
    for event in qa.answer(messages, book_ids=args.book_ids, top_k=args.top_k):
        if event["type"] == "delta":
            print(event["content"], end="", flush=True)
            answer_chars += len(event["content"])
        elif event["type"] == "citations":
            citations = event["citations"]

    print("\n--- citations ---")
    for i, c in enumerate(citations, 1):
        flag = " [SUMMARY]" if c["chunk_id"].endswith(":summary") else ""
        print(f"[{i}] score={c['score']:.3f} book={c['book_id'][:8]} chapter={c['chapter_id'][:8]}{flag}")
        print(f"    id={c['chunk_id']}")
        print(f"    {c['content'][:80]!r}")

    print(f"--- answer_chars={answer_chars} citations={len(citations)} ---")
    sys.exit(0 if answer_chars > 0 else 1)


if __name__ == "__main__":
    main()
