#!/usr/bin/env python3
"""Show global embedding/vector-store/database information for MyNexus.

Examples (run from the repository root):

    python3 scripts/embedding_info.py
    python3 scripts/embedding_info.py --json
    python3 scripts/embedding_info.py --no-coverage

This is a read-only diagnostic.  It opens the SQLite database in read-only
mode and reads the Chroma collection without creating one.  For per-book
details use scripts/book_embedding_info.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make sibling helper importable when executed as a file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _embedding_common import (  # noqa: E402
    compute_coverage,
    config_path,
    connect_db,
    database_counts,
    dump_json,
    fmt_int,
    fmt_pct,
    list_books,
    load_config,
    load_store,
    print_table,
    tokenizer_info,
)


def build_report(cfg, con, store, tinfo, coverage, db_counts, books):
    db_chunk_ids = {str(row["id"]) for row in con.execute("SELECT id FROM chunks").fetchall()}
    store_content_ids = set(store.content_ids())
    missing = sorted(db_chunk_ids - store_content_ids)
    orphan = sorted(store_content_ids - db_chunk_ids)
    expected_summary = db_counts["chapters_with_summary"] + db_counts["books_with_summary"]
    actual_summary = store.summary_count
    dimension = store.dim or tinfo.dim

    warnings: list[str] = []
    if not store.exists:
        warnings.append(f"vector store not found: {store.path}")
    if missing:
        warnings.append(f"{len(missing)} DB chunk(s) have no content vector")
    if orphan:
        warnings.append(f"{len(orphan)} content vector(s) have no DB chunk")
    if expected_summary != actual_summary:
        warnings.append(
            f"summary vectors={actual_summary}, expected={expected_summary} "
            "(summary count is DB summaries; stale vectors are possible)"
        )
    if store.dim and tinfo.dim and store.dim != tinfo.dim:
        warnings.append(
            f"stored vector dimension={store.dim} but configured model dimension={tinfo.dim}"
        )
    if coverage and coverage.over_limit_chunks:
        warnings.append(
            f"{fmt_int(coverage.over_limit_chunks)}/{fmt_int(coverage.total_chunks)} chunks "
            f"({fmt_pct(coverage.over_limit_pct)}) exceed the {tinfo.limit}-token input limit; "
            f"estimated unique chapter coverage is {fmt_pct(coverage.coverage_pct)}"
        )

    book_rows = []
    for book in books:
        row = con.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM chapters WHERE book_id = ?) AS chapters,
              (SELECT COUNT(*) FROM chunks WHERE book_id = ?) AS chunks,
              (SELECT COALESCE(SUM(LENGTH(content)), 0) FROM chapters WHERE book_id = ?) AS chars
            """,
            (book["id"], book["id"], book["id"]),
        ).fetchone()
        vector_ids, summary_ids = store.for_book(book["id"])
        book_rows.append(
            {
                "id": book["id"],
                "title": book["title"] or "",
                "author": book["author"] or "",
                "language": book["language"] or "",
                "source_format": book["source_format"] or "",
                "status": book["status"] or "",
                "chapters": int(row["chapters"] or 0),
                "chunks": int(row["chunks"] or 0),
                "chars": int(row["chars"] or 0),
                "vectors": len(vector_ids),
                "summary_vectors": len(summary_ids),
            }
        )

    coverage_dict = None
    if coverage is not None:
        stats = coverage.token_stats()
        coverage_dict = {
            "total_chars": coverage.total_chars,
            "covered_chars": coverage.covered_chars,
            "coverage_pct": round(coverage.coverage_pct, 1),
            "total_chunks": coverage.total_chunks,
            "over_limit_chunks": coverage.over_limit_chunks,
            "over_limit_pct": round(coverage.over_limit_pct, 1),
            "tokens_min": stats["min"],
            "tokens_median": stats["median"],
            "tokens_max": stats["max"],
        }

    return {
        "config_path": str(config_path()),
        "db_path": None,  # filled by main()
        "splitter": {
            "chunk_size": cfg.splitter.chunk_size,
            "chunk_overlap": cfg.splitter.chunk_overlap,
            "strategy": cfg.splitter.strategy,
        },
        "embedding": {
            "provider": tinfo.provider,
            "model": tinfo.model,
            "base_url": getattr(cfg.active_embedder, "base_url", "") or "",
            "dimension": dimension,
            "model_dimension": tinfo.dim,
            "model_size_gb": tinfo.size_gb,
            "description": tinfo.description,
            "token_limit": tinfo.limit,
            "token_limit_source": tinfo.limit_source,
            "tokenizer_path": tinfo.tokenizer_path,
            "tokenizer_max_length": tinfo.config_max_length,
            "tokenizer_model_max_length": tinfo.config_model_max_length,
        },
        "vector_store": {
            "backend": store.backend,
            "path": store.path,
            "exists": store.exists,
            "count": store.count,
            "content_count": store.content_count,
            "summary_count": actual_summary,
            "dimension": store.dim,
            "metadata": store.metadata,
        },
        "database": db_counts,
        "integrity": {
            "missing_vectors": len(missing),
            "orphan_vectors": len(orphan),
            "missing_examples": missing[:5],
            "orphan_examples": orphan[:5],
            "summary_expected": expected_summary,
            "summary_actual": actual_summary,
        },
        "coverage": coverage_dict,
        "coverage_skipped": False,
        "books": book_rows,
        "warnings": warnings,
    }


def print_report(report, db_path):
    embedding = report["embedding"]
    store = report["vector_store"]
    db_counts = report["database"]
    integrity = report["integrity"]
    coverage = report["coverage"]

    print()
    print("MyNexus embedding info")
    print("=======================")
    print(f"Config      : {report['config_path']}")
    print(f"Database    : {db_path}")
    print(f"Vector store: {store['backend']} @ {store['path']}")

    print()
    print("Embedding")
    print(f"  provider          : {embedding['provider']}")
    print(f"  model             : {embedding['model']}")
    if embedding["base_url"]:
        print(f"  base URL          : {embedding['base_url']}")
    if embedding["model_size_gb"]:
        print(f"  model size        : {embedding['model_size_gb']:.2f} GB")
    if embedding["dimension"] is not None:
        source = "vector store" if store["dimension"] is not None else "model metadata"
        print(f"  dimension         : {embedding['dimension']} (from {source})")
    if embedding["token_limit"] is not None:
        print(f"  input token limit : {embedding['token_limit']} ({embedding['token_limit_source']})")
    else:
        print(f"  input token limit : unknown ({embedding['token_limit_source']})")
    if embedding["tokenizer_path"]:
        print(f"  tokenizer         : {embedding['tokenizer_path']}")
    if embedding["description"]:
        print(f"  model note        : {embedding['description']}")

    print()
    print("Vector store")
    print(f"  backend          : {store['backend']}")
    print(f"  path             : {store['path']}")
    print(f"  exists           : {store['exists']}")
    print(f"  total vectors    : {fmt_int(store['count'])}")
    print(f"  content vectors  : {fmt_int(store['content_count'])}")
    print(f"  summary vectors  : {fmt_int(store['summary_count'])}")
    print(f"  dimension        : {store['dimension'] if store['dimension'] is not None else '-'}")
    if store["metadata"]:
        print(f"  metadata         : {store['metadata']}")

    print()
    print("Database")
    print(f"  books                  : {fmt_int(db_counts['books'])}")
    print(f"  chapters               : {fmt_int(db_counts['chapters'])}")
    print(f"  chunks                 : {fmt_int(db_counts['chunks'])}")
    print(f"  chapter characters     : {fmt_int(db_counts['chapter_chars'])}")
    print(f"  chunk characters       : {fmt_int(db_counts['chunk_chars'])} (includes chunk overlap)")
    print(f"  chapters with summary  : {fmt_int(db_counts['chapters_with_summary'])}")
    print(f"  book summaries         : {fmt_int(db_counts['books_with_summary'])}")

    splitter = report["splitter"]
    print()
    print("Splitter")
    print(f"  strategy        : {splitter['strategy']}")
    print(f"  chunk size      : {fmt_int(splitter['chunk_size'])} chars")
    print(f"  chunk overlap   : {fmt_int(splitter['chunk_overlap'])} chars")

    print()
    print("Token / coverage audit")
    if coverage is None:
        if report.get("coverage_skipped"):
            print("  skipped (--no-coverage)")
        else:
            print("  unavailable: local tokenizer not found, or provider is not local")
    else:
        print(f"  chunks over limit      : {fmt_int(coverage['over_limit_chunks'])} / "
              f"{fmt_int(coverage['total_chunks'])} ({fmt_pct(coverage['over_limit_pct'])})")
        print(f"  unique chapter coverage: {fmt_pct(coverage['coverage_pct'])} "
              f"({fmt_int(coverage['covered_chars'])} / {fmt_int(coverage['total_chars'])} chars)")
        print(f"  chunk token count      : min={coverage['tokens_min']} "
              f"median={coverage['tokens_median']} max={coverage['tokens_max']}")
        print("  method                 : union of characters in each chunk's first token-limit window")
        print("  note                   : DB chunks.token_count may use another tokenizer; this audit recounts with the embedding tokenizer")

    print()
    print("Books")
    print_table(
        ["ID", "Title", "Chapters", "Chunks", "Vectors", "Summary", "Chars"],
        [
            [
                book["id"],
                book["title"],
                book["chapters"],
                book["chunks"],
                book["vectors"],
                book["summary_vectors"],
                book["chars"],
            ]
            for book in report["books"]
        ],
        right_align={2, 3, 4, 5, 6},
        max_col_width=40,
    )

    print()
    print("Integrity")
    print(f"  missing content vectors : {fmt_int(integrity['missing_vectors'])}")
    print(f"  orphan content vectors  : {fmt_int(integrity['orphan_vectors'])}")
    print(f"  summary vectors         : {fmt_int(integrity['summary_actual'])} "
          f"(expected {fmt_int(integrity['summary_expected'])})")
    if integrity["missing_examples"]:
        print(f"    missing examples      : {', '.join(integrity['missing_examples'])}")
    if integrity["orphan_examples"]:
        print(f"    orphan examples       : {', '.join(integrity['orphan_examples'])}")

    if report["warnings"]:
        print()
        print("Warnings")
        for warning in report["warnings"]:
            print(f"  ! {warning}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Show global MyNexus embedding and vector-store information.")
    parser.add_argument("--config", help="path to config.yaml (default: MYNEXUS_CONFIG_PATH or config/config.yaml)")
    parser.add_argument("--db", help="path to the SQLite database (default: config storage.sqlite.path)")
    parser.add_argument("--vectorstore", help="path to the vector store (default: config storage.vector_store_path)")
    parser.add_argument("--no-coverage", action="store_true", help="skip tokenizing every chunk for coverage stats")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON only")
    args = parser.parse_args()

    cfg = load_config(args.config)
    con, db_path = connect_db(cfg, args.db)
    store = load_store(cfg, args.vectorstore)
    tinfo = tokenizer_info(cfg)
    db_counts = database_counts(con)
    books = list_books(con)
    coverage = None if args.no_coverage else compute_coverage(con, tinfo)

    report = build_report(cfg, con, store, tinfo, coverage, db_counts, books)
    report["db_path"] = str(db_path)
    report["coverage_skipped"] = args.no_coverage

    if args.json:
        dump_json(report)
    else:
        print_report(report, db_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
