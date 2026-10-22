#!/usr/bin/env python3
"""Measure retrieval recall for chunks whose text lies outside the embedding window.

The earlier audit (with 500-character chunks) showed that the local MiniLM
model only encodes the first 128 tokens of each chunk.  This script turns that
finding into a repeatable test:

  * sample chunks (balanced across books by default)
  * build a query from the chunk's *tail* (text the model cannot see) or head
  * search for the source chunk by vector and/or hybrid retrieval
  * report hit@1/5/10/top-k and MRR

Examples (run from the repository root):

    # current local model, all books, 20 tail queries
    python3 scripts/embedding_recall_test.py --samples 20

    # one book, compare vector and hybrid, 10 tail queries per book
    python3 scripts/embedding_recall_test.py \
        --book-id <book-id> --samples-per-book 10 --mode both

    # after switching to a long-context model, use head/random queries
    python3 scripts/embedding_recall_test.py --samples 20 --query-source head

The script reads SQLite and the vector store directly; it does not need the
Worker or Core API to be running (the local embedding model is loaded in this
process).
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _embedding_common import (  # noqa: E402
    chunk_covered_chars,
    clip,
    config_path,
    connect_db,
    dump_json,
    fmt_pct,
    get_book,
    list_books,
    load_config,
    load_store,
    print_table,
    tokenizer_info,
    vector_store_path,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?])\s*|\n+|(?<=\.)\s+")


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT.split(text) if part and part.strip()]


def _tail_start(row: Any, tinfo, args) -> int:
    content = row["content"] or ""
    if tinfo.tokenizer is not None and tinfo.limit:
        covered, _ = chunk_covered_chars(tinfo.tokenizer, content, tinfo.limit)
        return min(covered, len(content))
    return min(int(len(content) * (1.0 - args.tail_fraction)), len(content))


def _make_query(row: Any, source: str, tinfo, args, rng: random.Random) -> tuple[str | None, int | None]:
    """Return (query, tail_chars) or (None, tail_chars) if this chunk is unusable."""
    content = row["content"] or ""
    if len(content) < args.min_query_chars:
        return None, None

    if source == "head":
        region = content[: max(args.query_chars * 2, 200)].strip()
        parts = [part for part in _sentences(region) if len(part) >= args.min_query_chars]
        query = parts[0] if parts else region[: args.query_chars]
        return query[: args.query_chars].strip() or None, None

    if source == "random":
        parts = [part for part in _sentences(content) if len(part) >= args.min_query_chars]
        query = rng.choice(parts) if parts else content[: args.query_chars]
        return query[: args.query_chars].strip() or None, None

    # tail
    start = _tail_start(row, tinfo, args)
    tail = content[start:].strip()
    tail_chars = len(content) - start
    if len(tail) < args.min_tail_chars:
        return None, tail_chars
    parts = [part for part in _sentences(tail) if len(part) >= args.min_query_chars]
    query = parts[-1] if parts else tail[-args.query_chars :]
    return query[: args.query_chars].strip() or None, tail_chars


def _candidate_rows(rows: Sequence[Any], source: str, tinfo, args) -> dict[str, list[Any]]:
    by_book: dict[str, list[Any]] = {}
    for row in rows:
        content = row["content"] or ""
        if len(content) < args.min_query_chars:
            continue
        if source == "tail":
            start = _tail_start(row, tinfo, args)
            if len(content) - start < args.min_tail_chars:
                continue
        by_book.setdefault(row["book_id"], []).append(row)
    return by_book


def _sample_rows(
    by_book: dict[str, list[Any]],
    book_ids: Sequence[str],
    samples: int,
    samples_per_book: int | None,
    seed: int,
) -> list[Any]:
    rng = random.Random(seed)
    for book_id in book_ids:
        rng.shuffle(by_book.get(book_id, []))

    if samples_per_book is not None:
        picked: list[Any] = []
        for book_id in book_ids:
            picked.extend(by_book.get(book_id, [])[:samples_per_book])
        return picked

    picked = []
    cursor = {book_id: 0 for book_id in book_ids}
    while len(picked) < samples:
        added = False
        for book_id in book_ids:
            if len(picked) >= samples:
                break
            rows = by_book.get(book_id, [])
            index = cursor[book_id]
            if index < len(rows):
                picked.append(rows[index])
                cursor[book_id] = index + 1
                added = True
        if not added:
            break
    return picked


def _metrics(ranks: Sequence[int], top_k: int) -> dict[str, Any]:
    n = len(ranks)
    ks = sorted({1, 5, 10, top_k})
    result: dict[str, Any] = {"n": n}
    for k in ks:
        result[f"hit@{k}"] = {
            "count": sum(1 for rank in ranks if 0 < rank <= k),
            "pct": round(sum(1 for rank in ranks if 0 < rank <= k) / n * 100.0, 1) if n else 0.0,
        }
    result["mrr"] = round(sum(1.0 / rank for rank in ranks if rank > 0) / n, 4) if n else 0.0
    return result


def _scope_key(scope_ids: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(scope_ids) if scope_ids else ("<all>",)


class RecallRunner:
    def __init__(self, cfg, args):
        # Imported lazily so `load_config()` has already put worker/src on
        # sys.path.  RetrievalPipeline owns the embedder, vector store and
        # BM25 implementation, so vector and hybrid tests use identical
        # scoring paths to production QA.
        from pipelines.retrieval import RetrievalPipeline  # noqa: PLC0415

        self.args = args
        self.retrieval = RetrievalPipeline(cfg)
        self.tinfo = tokenizer_info(cfg)
        self._scope_cache: dict[tuple[str, ...], tuple[list[dict], list[dict], dict[str, int]]] = {}

    def _scope_data(self, scope_ids: Sequence[str] | None):
        key = _scope_key(scope_ids)
        if key not in self._scope_cache:
            records = self.retrieval.vector_store.all(list(scope_ids) if scope_ids else None)
            content = [record for record in records if not record["id"].endswith(":summary")]
            by_id = {record["id"]: index for index, record in enumerate(content)}
            self._scope_cache[key] = (records, content, by_id)
        return self._scope_cache[key]

    def vector_rank(self, query: str, chunk_id: str, scope_ids: Sequence[str] | None) -> tuple[int, float | None]:
        records, content, _ = self._scope_data(scope_ids)
        if not content:
            return 0, None
        query_vector = self.retrieval.embedder.process([query])[0]
        # Ask for every vector in scope; filtering summaries below keeps
        # ranks comparable to QA, which excludes summary pseudo-chunks.
        results = self.retrieval.vector_store.search(
            query_vector,
            top_k=len(records),
            book_ids=list(scope_ids) if scope_ids else None,
        )
        content_rank = 0
        for record in results:
            if record["id"].endswith(":summary"):
                continue
            content_rank += 1
            if record["id"] == chunk_id:
                return content_rank, float(record.get("score", 0.0))
        return 0, None

    def hybrid_rank(self, query: str, chunk_id: str, scope_ids: Sequence[str] | None) -> tuple[int, float | None]:
        _, content, _ = self._scope_data(scope_ids)
        if not content:
            return 0, None
        results = self.retrieval.search(
            query,
            book_ids=list(scope_ids) if scope_ids else None,
            top_k=len(content),
            mode="hybrid",
        )
        for index, record in enumerate(results, start=1):
            if record["id"] == chunk_id:
                return index, float(record.get("score", 0.0))
        return 0, None


def _scope_ids_for(row: Any, selected_book_ids: Sequence[str], scope: str) -> list[str] | None:
    if scope == "all":
        return None
    if scope == "selection":
        return list(selected_book_ids)
    return [row["book_id"]]


def build_source_result(
    runner: RecallRunner,
    rows: Sequence[Any],
    source: str,
    selected_book_ids: Sequence[str],
    args,
) -> dict[str, Any]:
    by_book = _candidate_rows(rows, source, runner.tinfo, args)
    sample_rows = _sample_rows(
        by_book,
        selected_book_ids,
        args.samples,
        args.samples_per_book,
        args.seed,
    )
    rng = random.Random(args.seed)

    samples: list[dict[str, Any]] = []
    ranks_by_mode: dict[str, list[int]] = {mode: [] for mode in _modes(args.mode)}
    warnings: list[str] = []
    requested = (
        args.samples_per_book * len(selected_book_ids)
        if args.samples_per_book is not None
        else args.samples
    )
    if len(sample_rows) < requested:
        warnings.append(
            f"only {len(sample_rows)} usable chunk(s) for {source} queries; "
            f"requested {requested}"
        )

    for row in sample_rows:
        query, tail_chars = _make_query(row, source, runner.tinfo, args, rng)
        if not query:
            continue
        scope_ids = _scope_ids_for(row, selected_book_ids, args.scope)
        _, _, by_id = runner._scope_data(scope_ids)
        modes = _modes(args.mode)
        if row["id"] not in by_id:
            warnings.append(f"source chunk {row['id']} has no content vector")
            vector_rank, vector_score = (0, None) if "vector" in modes else (None, None)
            hybrid_rank, hybrid_score = (0, None) if "hybrid" in modes else (None, None)
        else:
            vector_rank, vector_score = (
                runner.vector_rank(query, row["id"], scope_ids)
                if "vector" in modes
                else (None, None)
            )
            hybrid_rank, hybrid_score = (
                runner.hybrid_rank(query, row["id"], scope_ids)
                if "hybrid" in modes
                else (None, None)
            )

        record: dict[str, Any] = {
            "book_id": row["book_id"],
            "book_title": row["book_title"],
            "chapter_id": row["chapter_id"],
            "chapter_title": row["chapter_title"],
            "chunk_id": row["id"],
            "position": row["position"],
            "query": query,
            "query_chars": len(query),
            "tail_chars": tail_chars,
            "ranks": {},
            "scores": {},
        }
        if vector_rank is not None:
            record["ranks"]["vector"] = vector_rank
            record["scores"]["vector"] = vector_score
            ranks_by_mode["vector"].append(vector_rank)
        if hybrid_rank is not None:
            record["ranks"]["hybrid"] = hybrid_rank
            record["scores"]["hybrid"] = hybrid_score
            ranks_by_mode["hybrid"].append(hybrid_rank)
        samples.append(record)

    if not samples:
        if source == "tail" and runner.tinfo.tokenizer is not None and runner.tinfo.limit:
            warnings.append(
                "no chunk has a tail beyond the model input limit; "
                "use --query-source head/random for this embedding model"
            )

    return {
        "source": source,
        "samples": samples,
        "metrics": {
            mode: _metrics(ranks, args.top_k)
            for mode, ranks in ranks_by_mode.items()
            if ranks or args.mode == mode
        },
        "warnings": warnings,
    }


def _modes(mode: str) -> list[str]:
    return ["vector", "hybrid"] if mode == "both" else [mode]


def print_source_result(result: dict[str, Any], args) -> None:
    source = result["source"]
    samples = result["samples"]
    print()
    print(f"Recall source: {source}")
    if not samples:
        print("  no usable samples")
        for warning in result["warnings"]:
            print(f"  ! {warning}")
        return

    print(f"  samples: {len(samples)}  top_k: {args.top_k}  scope: {args.scope}")
    print_table(
        ["#", "Book", "Chapter", "Rank vector", "Rank hybrid", "Query"],
        [
            [
                index,
                clip(sample["book_title"], 18),
                clip(sample["chapter_title"], 22),
                sample["ranks"].get("vector", "-"),
                sample["ranks"].get("hybrid", "-"),
                clip(sample["query"], 52),
            ]
            for index, sample in enumerate(samples, start=1)
        ],
        right_align={0, 3, 4},
        max_col_width=52,
    )

    for mode in _modes(args.mode):
        metrics = result["metrics"].get(mode)
        if not metrics:
            continue
        print()
        print(f"  {source} / {mode} metrics")
        for key in sorted((k for k in metrics if k.startswith("hit@")), key=lambda k: int(k.split("@")[1])):
            value = metrics[key]
            print(f"    {key:<8}: {value['count']}/{metrics['n']} ({fmt_pct(value['pct'])})")
        print(f"    MRR     : {metrics['mrr']:.4f}")

    if result["warnings"]:
        print()
        for warning in result["warnings"]:
            print(f"  ! {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure vector/hybrid retrieval recall for chunk heads and tails."
    )
    parser.add_argument("--config", help="path to config.yaml (default: MYNEXUS_CONFIG_PATH or config/config.yaml)")
    parser.add_argument("--db", help="path to the SQLite database (default: config storage.sqlite.path)")
    parser.add_argument("--vectorstore", help="path to the vector store (default: config storage.vector_store_path)")
    parser.add_argument(
        "--book-id",
        action="append",
        dest="book_ids",
        help="book id to test (repeatable); default: all books",
    )
    parser.add_argument("--samples", type=int, default=20, help="total samples, balanced across books (default: 20)")
    parser.add_argument("--samples-per-book", type=int, help="sample this many chunks from every selected book")
    parser.add_argument(
        "--query-source",
        choices=("tail", "head", "random", "both"),
        default="tail",
        help="where to take the query text from; both = head + tail (default: tail)",
    )
    parser.add_argument("--query-chars", type=int, default=80, help="maximum query length in characters (default: 80)")
    parser.add_argument("--min-query-chars", type=int, default=12, help="minimum query length (default: 12)")
    parser.add_argument("--min-tail-chars", type=int, default=12, help="minimum unseen tail length (default: 12)")
    parser.add_argument(
        "--tail-fraction",
        type=float,
        default=0.25,
        help="fallback tail fraction when no local tokenizer is available (default: 0.25)",
    )
    parser.add_argument("--top-k", type=int, default=30, help="largest cut-off to report (default: 30)")
    parser.add_argument(
        "--mode",
        choices=("vector", "hybrid", "both"),
        default="vector",
        help="retrieval mode to test (default: vector)",
    )
    parser.add_argument(
        "--scope",
        choices=("book", "selection", "all"),
        default="book",
        help="search within the source book, all selected books, or all books (default: book)",
    )
    parser.add_argument("--seed", type=int, default=42, help="sampling/query seed (default: 42)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON only")
    args = parser.parse_args()

    if args.samples <= 0 and not args.samples_per_book:
        parser.error("--samples must be positive")
    if args.samples_per_book is not None and args.samples_per_book <= 0:
        parser.error("--samples-per-book must be positive")
    if args.top_k <= 0:
        parser.error("--top-k must be positive")
    if not 0.0 < args.tail_fraction < 1.0:
        parser.error("--tail-fraction must be between 0 and 1")

    cfg = load_config(args.config)
    if args.vectorstore:
        # RetrievalPipeline reads cfg.vector_store_path, so the CLI override
        # must be applied before constructing it.
        cfg.vector_store_path = str(vector_store_path(cfg, args.vectorstore))
    con, db_path = connect_db(cfg, args.db)

    if args.book_ids:
        books = [get_book(con, book_id) for book_id in args.book_ids]
    else:
        books = list_books(con)
    if not books:
        print("no books found", file=sys.stderr)
        return 2

    selected_book_ids = [book["id"] for book in books]
    store = load_store(cfg, args.vectorstore)
    runner = RecallRunner(cfg, args)

    rows = [
        row
        for row in _chunk_rows(con, selected_book_ids)
        if row["book_id"] in selected_book_ids
    ]
    if not rows:
        print("no chunks found for the selected book(s)", file=sys.stderr)
        return 2

    sources = ["head", "tail"] if args.query_source == "both" else [args.query_source]
    report: dict[str, Any] = {
        "config_path": str(config_path()),
        "db_path": str(db_path),
        "embedding": {
            "provider": cfg.embedding_provider,
            "model": cfg.active_embedder.model,
            "token_limit": runner.tinfo.limit,
            "token_limit_source": runner.tinfo.limit_source,
            "dimension": store.dim or runner.tinfo.dim,
        },
        "books": [
            {"id": book["id"], "title": book["title"] or ""}
            for book in books
        ],
        "scope": args.scope,
        "mode": args.mode,
        "top_k": args.top_k,
        "seed": args.seed,
        "sources": {},
    }

    for source in sources:
        report["sources"][source] = build_source_result(
            runner, rows, source, selected_book_ids, args
        )

    if args.json:
        dump_json(report)
        return 0

    print()
    print("MyNexus embedding recall test")
    print("=============================")
    print(f"Config      : {report['config_path']}")
    print(f"Database    : {report['db_path']}")
    print(f"Model       : {report['embedding']['model']} ({report['embedding']['provider']})")
    if report["embedding"]["dimension"] is not None:
        print(f"Dimension   : {report['embedding']['dimension']}")
    if report["embedding"]["token_limit"] is not None:
        print(f"Token limit : {report['embedding']['token_limit']} "
              f"({report['embedding']['token_limit_source']})")
    else:
        print(f"Token limit : unknown ({report['embedding']['token_limit_source']})")
    print(f"Books       : {', '.join(book['title'] for book in report['books'])}")
    print(f"Scope       : {args.scope}   Mode: {args.mode}   Seed: {args.seed}")
    if runner.tinfo.tokenizer is None and "tail" in sources:
        print(f"Tail source : last {args.tail_fraction:.0%} of each chunk "
              "(no local tokenizer available)")

    for source in sources:
        print_source_result(report["sources"][source], args)

    print()
    return 0


def _chunk_rows(con, book_ids: Sequence[str]) -> list[Any]:
    """Fetch chunks for the selected books with their chapter titles."""
    rows: list[Any] = []
    for book_id in book_ids:
        rows.extend(
            con.execute(
                """
                SELECT
                  c.id, c.book_id, b.title AS book_title,
                  c.chapter_id, ch.title AS chapter_title,
                  ch.sort_order, c.content, c.position
                FROM chunks c
                JOIN chapters ch ON ch.id = c.chapter_id
                JOIN books b ON b.id = c.book_id
                WHERE c.book_id = ?
                ORDER BY ch.sort_order, c.position
                """,
                (book_id,),
            ).fetchall()
        )
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
