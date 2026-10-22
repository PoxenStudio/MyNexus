#!/usr/bin/env python3
"""Show embedding/vector-store information for one MyNexus book.

Examples (run from the repository root):

    python3 scripts/book_embedding_info.py <book-id>
    python3 scripts/book_embedding_info.py <book-id> --chapters
    python3 scripts/book_embedding_info.py <book-id> --json

This is a read-only diagnostic.  It reports the book's DB chunk count, vector
count/dimension, missing or orphan vectors, summary vectors, token-limit
overflow and unique chapter coverage.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _embedding_common import (  # noqa: E402
    book_database_counts,
    compute_coverage,
    config_path,
    connect_db,
    dump_json,
    fmt_int,
    fmt_pct,
    get_book,
    load_config,
    load_store,
    print_table,
    tokenizer_info,
)


def build_report(cfg, con, store, tinfo, book, coverage, include_chapters):
    book_id = book["id"]
    db_counts = book_database_counts(con, book_id)
    vector_ids, summary_ids = store.for_book(book_id)
    db_chunk_ids = {
        str(row["id"])
        for row in con.execute("SELECT id FROM chunks WHERE book_id = ?", (book_id,)).fetchall()
    }
    content_ids = set(vector_ids)
    missing = sorted(db_chunk_ids - content_ids)
    orphan = sorted(content_ids - db_chunk_ids)
    expected_summary = db_counts["chapters_with_summary"] + db_counts["books_with_summary"]
    dimension = store.dim or tinfo.dim

    warnings: list[str] = []
    if not vector_ids and not summary_ids:
        warnings.append(f"no vectors found for book {book_id}")
    if missing:
        warnings.append(f"{len(missing)} DB chunk(s) have no content vector")
    if orphan:
        warnings.append(f"{len(orphan)} content vector(s) have no DB chunk")
    if expected_summary != len(summary_ids):
        warnings.append(
            f"summary vectors={len(summary_ids)}, expected={expected_summary} "
            "(stale vectors are possible)"
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

    coverage_dict = None
    chapter_rows = []
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
        if include_chapters:
            for chapter in coverage.chapters:
                pct = (
                    chapter["covered_chars"] / chapter["total_chars"] * 100.0
                    if chapter["total_chars"]
                    else 0.0
                )
                chapter_rows.append(
                    {
                        "chapter_id": chapter["chapter_id"],
                        "title": chapter["title"],
                        "sort_order": chapter["sort_order"],
                        "chunks": chapter["chunks"],
                        "chars": chapter["total_chars"],
                        "covered_chars": chapter["covered_chars"],
                        "coverage_pct": round(pct, 1),
                        "over_limit_chunks": chapter["over_limit_chunks"],
                    }
                )

    return {
        "config_path": str(config_path()),
        "book": {
            "id": book["id"],
            "title": book["title"] or "",
            "author": book["author"] or "",
            "language": book["language"] or "",
            "source_format": book["source_format"] or "",
            "status": book["status"] or "",
            "created_at": book["created_at"] or "",
        },
        "splitter": {
            "chunk_size": cfg.splitter.chunk_size,
            "chunk_overlap": cfg.splitter.chunk_overlap,
            "strategy": cfg.splitter.strategy,
        },
        "embedding": {
            "provider": tinfo.provider,
            "model": tinfo.model,
            "dimension": dimension,
            "model_dimension": tinfo.dim,
            "token_limit": tinfo.limit,
            "token_limit_source": tinfo.limit_source,
            "tokenizer_path": tinfo.tokenizer_path,
        },
        "database": db_counts,
        "vectors": {
            "backend": store.backend,
            "path": store.path,
            "content_count": len(vector_ids),
            "summary_count": len(summary_ids),
            "total_count": len(vector_ids) + len(summary_ids),
            "dimension": store.dim,
            "missing": len(missing),
            "orphan": len(orphan),
            "missing_examples": missing[:5],
            "orphan_examples": orphan[:5],
        },
        "coverage": coverage_dict,
        "coverage_skipped": False,
        "chapters": chapter_rows if include_chapters else [],
        "warnings": warnings,
    }


def print_report(report, db_path=None):
    book = report["book"]
    embedding = report["embedding"]
    db_counts = report["database"]
    vectors = report["vectors"]
    coverage = report["coverage"]

    print()
    print("Book embedding info")
    print("===================")
    print(f"Config      : {report['config_path']}")
    if db_path:
        print(f"Database    : {db_path}")
    print(f"Vector store: {vectors['backend']} @ {vectors['path']}")

    print()
    print("Book")
    print(f"  id           : {book['id']}")
    print(f"  title        : {book['title']}")
    print(f"  author       : {book['author']}")
    print(f"  language     : {book['language']}")
    print(f"  source format: {book['source_format']}")
    print(f"  status       : {book['status']}")
    print(f"  created at   : {book['created_at']}")

    print()
    print("Embedding")
    print(f"  provider          : {embedding['provider']}")
    print(f"  model             : {embedding['model']}")
    if embedding["dimension"] is not None:
        source = "vector store" if vectors["dimension"] is not None else "model metadata"
        print(f"  dimension         : {embedding['dimension']} (from {source})")
    if embedding["token_limit"] is not None:
        print(f"  input token limit : {embedding['token_limit']} ({embedding['token_limit_source']})")
    else:
        print(f"  input token limit : unknown ({embedding['token_limit_source']})")
    if embedding["tokenizer_path"]:
        print(f"  tokenizer         : {embedding['tokenizer_path']}")

    print()
    print("Database")
    print(f"  chapters              : {fmt_int(db_counts['chapters'])}")
    print(f"  chunks                : {fmt_int(db_counts['chunks'])}")
    print(f"  chapter characters    : {fmt_int(db_counts['chapter_chars'])}")
    print(f"  chunk characters      : {fmt_int(db_counts['chunk_chars'])} (includes chunk overlap)")
    print(f"  chapters with summary : {fmt_int(db_counts['chapters_with_summary'])}")
    print(f"  book summary          : {fmt_int(db_counts['books_with_summary'])}")

    print()
    print("Vectors")
    print(f"  content vectors : {fmt_int(vectors['content_count'])}")
    print(f"  summary vectors : {fmt_int(vectors['summary_count'])}")
    print(f"  total vectors   : {fmt_int(vectors['total_count'])}")
    print(f"  dimension       : {vectors['dimension'] if vectors['dimension'] is not None else '-'}")
    print(f"  missing vectors : {fmt_int(vectors['missing'])}")
    print(f"  orphan vectors  : {fmt_int(vectors['orphan'])}")
    if vectors["missing_examples"]:
        print(f"    missing examples: {', '.join(vectors['missing_examples'])}")
    if vectors["orphan_examples"]:
        print(f"    orphan examples : {', '.join(vectors['orphan_examples'])}")

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

    if report["chapters"]:
        print()
        print("Chapters")
        print_table(
            ["#", "Title", "Chunks", "Chars", "Covered", "Coverage", "Over"],
            [
                [
                    chapter["sort_order"],
                    chapter["title"],
                    chapter["chunks"],
                    chapter["chars"],
                    chapter["covered_chars"],
                    fmt_pct(chapter["coverage_pct"]),
                    chapter["over_limit_chunks"],
                ]
                for chapter in report["chapters"]
            ],
            right_align={0, 2, 3, 4, 5, 6},
            max_col_width=44,
        )

    if report["warnings"]:
        print()
        print("Warnings")
        for warning in report["warnings"]:
            print(f"  ! {warning}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Show embedding information for one MyNexus book.")
    parser.add_argument("book_id", help="MyNexus book id (UUID)")
    parser.add_argument("--config", help="path to config.yaml (default: MYNEXUS_CONFIG_PATH or config/config.yaml)")
    parser.add_argument("--db", help="path to the SQLite database (default: config storage.sqlite.path)")
    parser.add_argument("--vectorstore", help="path to the vector store (default: config storage.vector_store_path)")
    parser.add_argument("--chapters", action="store_true", help="also print per-chapter chunk/coverage stats")
    parser.add_argument("--no-coverage", action="store_true", help="skip tokenizing every chunk for coverage stats")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON only")
    args = parser.parse_args()

    cfg = load_config(args.config)
    con, db_path = connect_db(cfg, args.db)
    book = get_book(con, args.book_id)
    store = load_store(cfg, args.vectorstore)
    tinfo = tokenizer_info(cfg)
    coverage = (
        None
        if args.no_coverage
        else compute_coverage(con, tinfo, [args.book_id], include_chapters=args.chapters)
    )
    report = build_report(cfg, con, store, tinfo, book, coverage, args.chapters)
    report["coverage_skipped"] = args.no_coverage

    if args.json:
        report["db_path"] = str(db_path)
        dump_json(report)
    else:
        print_report(report, db_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
