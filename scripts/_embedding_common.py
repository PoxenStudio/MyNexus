#!/usr/bin/env python3
"""Shared helpers for the embedding diagnostics scripts.

These scripts intentionally read the same config.yaml, SQLite database and
vector store as the Worker.  They do not call Core API/Worker and never write
to the database or vector store.

Typical invocation (from the repository root):

    python3 scripts/embedding_info.py
    python3 scripts/book_embedding_info.py <book-id>
    python3 scripts/embedding_recall_test.py --samples 20

The host Python needs the Worker dependencies installed (chromadb, fastembed,
tokenizers, ...).  Postgres-backed deployments are not supported by these
diagnostics; they need direct SQLite access to chunk offsets.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
WORKER_SRC = ROOT / "worker" / "src"
DEFAULT_CONFIG_PATH = ROOT / "config" / "config.yaml"

# Models with a context limit that is not visible in a local tokenizer file.
# Values are the documented maximum input tokens, not an embedding dimension.
_KNOWN_TOKEN_LIMITS: dict[str, int] = {
    "bge-m3": 8192,
    "nomic-embed-text": 8192,
    "mxbai-embed-large": 512,
    "text-embedding-3-small": 8191,
    "text-embedding-3-large": 8191,
    "text-embedding-ada-002": 8191,
}

# Used only when a provider does not expose a local model/tokenizer file.
_KNOWN_DIMENSIONS: dict[str, int] = {
    "bge-m3": 1024,
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def _ensure_worker_on_path() -> None:
    worker = str(WORKER_SRC)
    if worker not in sys.path:
        sys.path.insert(0, worker)


def load_config(config_path: str | Path | None = None):
    """Load WorkerConfig, resolving paths against the repository root.

    ``config.py`` resolves relative paths against the current directory.  The
    diagnostics are meant to be run from the repo root, but resolving the
    important data paths here also makes them work from ``scripts/``.
    """
    _ensure_worker_on_path()
    if config_path:
        os.environ["MYNEXUS_CONFIG_PATH"] = str(Path(config_path).expanduser().resolve())
    else:
        os.environ.setdefault("MYNEXUS_CONFIG_PATH", str(DEFAULT_CONFIG_PATH))

    from config import load_config as _load_config  # noqa: PLC0415

    cfg = _load_config()
    cfg.vector_store_path = str(resolve_data_path(cfg.vector_store_path))
    if cfg.embedding_local_model_path:
        cfg.embedding_local_model_path = str(resolve_data_path(cfg.embedding_local_model_path))
    return cfg


def config_path() -> Path:
    return Path(os.environ.get("MYNEXUS_CONFIG_PATH", str(DEFAULT_CONFIG_PATH))).expanduser().resolve()


def resolve_data_path(value: str | Path) -> Path:
    """Resolve a config-relative data path.

    Prefer a path that already exists relative to the caller's cwd (the common
    case for commands run at the repo root), otherwise anchor it at the repo
    root.  Absolute paths are returned unchanged.
    """
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def sqlite_path(cfg) -> Path:
    env_path = os.getenv("MYNEXUS_STORAGE_SQLITE_PATH")
    raw_path = (
        env_path
        or cfg.raw.get("storage", {}).get("sqlite", {}).get("path")
        or "./data/mynexus.db"
    )
    return resolve_data_path(raw_path)


def vector_store_path(cfg, override: str | None = None) -> Path:
    return resolve_data_path(override or cfg.vector_store_path)


def connect_db(cfg, path: str | Path | None = None) -> tuple[sqlite3.Connection, Path]:
    if cfg.storage_database != "sqlite":
        raise RuntimeError(
            f"storage.database={cfg.storage_database!r} is configured; these diagnostics "
            "need a SQLite database (they read chunk offsets directly). Point --db at "
            "a local SQLite copy or run them against the dev SQLite setup."
        )
    db_path = resolve_data_path(path) if path else sqlite_path(cfg)
    if not db_path.exists():
        raise FileNotFoundError(
            f"SQLite database not found: {db_path}\n"
            "Start the dev services with `make dev-up` or pass --db explicitly."
        )
    # Read-only: these tools must never modify the live database.
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = ON")
    return con, db_path


def list_books(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT id, title, author, language, source_format, status, created_at "
        "FROM books ORDER BY title"
    ).fetchall()


def get_book(con: sqlite3.Connection, book_id: str) -> sqlite3.Row:
    row = con.execute(
        "SELECT id, title, author, language, source_format, status, created_at "
        "FROM books WHERE id = ?",
        (book_id,),
    ).fetchone()
    if row is None:
        available = list_books(con)
        lines = [f"book id not found: {book_id}"]
        if available:
            lines.append("available books:")
            lines.extend(f"  {r['id']}  {r['title']}" for r in available)
        raise SystemExit("\n".join(lines))
    return row


def database_counts(con: sqlite3.Connection) -> dict[str, int]:
    row = con.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM books) AS books,
          (SELECT COUNT(*) FROM chapters) AS chapters,
          (SELECT COUNT(*) FROM chunks) AS chunks,
          (SELECT COALESCE(SUM(LENGTH(content)), 0) FROM chapters) AS chapter_chars,
          (SELECT COALESCE(SUM(LENGTH(content)), 0) FROM chunks) AS chunk_chars,
          (SELECT COUNT(*) FROM chapters
             WHERE LENGTH(TRIM(COALESCE(summary, ''))) > 0) AS chapters_with_summary,
          (SELECT COUNT(*) FROM books
             WHERE LENGTH(TRIM(COALESCE(summary, ''))) > 0) AS books_with_summary
        """
    ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}


def book_database_counts(con: sqlite3.Connection, book_id: str) -> dict[str, int]:
    row = con.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM chapters WHERE book_id = ?) AS chapters,
          (SELECT COUNT(*) FROM chunks WHERE book_id = ?) AS chunks,
          (SELECT COALESCE(SUM(LENGTH(content)), 0) FROM chapters WHERE book_id = ?) AS chapter_chars,
          (SELECT COALESCE(SUM(LENGTH(content)), 0) FROM chunks WHERE book_id = ?) AS chunk_chars,
          (SELECT COUNT(*) FROM chapters
             WHERE book_id = ? AND LENGTH(TRIM(COALESCE(summary, ''))) > 0) AS chapters_with_summary,
          (SELECT COUNT(*) FROM books
             WHERE id = ? AND LENGTH(TRIM(COALESCE(summary, ''))) > 0) AS books_with_summary
        """,
        (book_id, book_id, book_id, book_id, book_id, book_id),
    ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}


def iter_chunks(con: sqlite3.Connection, book_id: str | None = None) -> list[sqlite3.Row]:
    sql = """
        SELECT
          c.id, c.book_id, c.chapter_id, ch.title AS chapter_title,
          ch.sort_order, c.content, c.token_count, c.position,
          c.start_offset, c.end_offset
        FROM chunks c
        JOIN chapters ch ON ch.id = c.chapter_id
    """
    params: tuple[Any, ...] = ()
    if book_id:
        sql += " WHERE c.book_id = ?"
        params = (book_id,)
    sql += " ORDER BY c.book_id, ch.sort_order, c.position"
    return con.execute(sql, params).fetchall()


@dataclass
class StoreInfo:
    backend: str
    path: str
    exists: bool = False
    count: int = 0
    dim: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ids: list[str] = field(default_factory=list)
    # book_id -> content vector ids / summary vector ids
    book_ids: dict[str, list[str]] = field(default_factory=dict)
    book_summary_ids: dict[str, list[str]] = field(default_factory=dict)

    @property
    def summary_count(self) -> int:
        return sum(len(v) for v in self.book_summary_ids.values())

    @property
    def content_count(self) -> int:
        return self.count - self.summary_count

    def content_ids(self) -> list[str]:
        return [i for i in self.ids if not i.endswith(":summary")]

    def for_book(self, book_id: str) -> tuple[list[str], list[str]]:
        return (
            self.book_ids.get(book_id, []),
            self.book_summary_ids.get(book_id, []),
        )


def _record_is_summary(chunk_id: str) -> bool:
    return chunk_id.endswith(":summary")


def load_store(cfg, path: str | Path | None = None) -> StoreInfo:
    """Read vector ids/metadata without writing to the vector store.

    Chroma's client is opened read-mostly: we use get_collection() directly,
    never get_or_create_collection(), so a missing collection does not create
    one as a side effect.
    """
    store_path = vector_store_path(cfg, str(path) if path else None)
    backend = cfg.vector_store
    if backend == "local":
        return _load_simple_store(store_path)
    return _load_chroma_store(store_path)


def _empty_store(backend: str, path: Path) -> StoreInfo:
    return StoreInfo(backend=backend, path=str(path), exists=False)


def _load_simple_store(path: Path) -> StoreInfo:
    file_path = path / "chunks.json"
    if not file_path.exists():
        return _empty_store("local", path)
    with file_path.open("r", encoding="utf-8") as f:
        records = json.load(f)

    info = StoreInfo(backend="local", path=str(path), exists=True, count=len(records))
    for record in records:
        chunk_id = str(record.get("id", ""))
        book_id = str(record.get("book_id", ""))
        info.ids.append(chunk_id)
        if _record_is_summary(chunk_id):
            info.book_summary_ids.setdefault(book_id, []).append(chunk_id)
        else:
            info.book_ids.setdefault(book_id, []).append(chunk_id)
        vector = record.get("vector") or []
        if info.dim is None and vector:
            info.dim = len(vector)
    return info


def _load_chroma_store(path: Path) -> StoreInfo:
    if not path.exists():
        return _empty_store("chroma", path)

    import chromadb  # noqa: PLC0415

    client = chromadb.PersistentClient(path=str(path))
    try:
        collection = client.get_collection("chunks")
    except Exception:
        return _empty_store("chroma", path)

    info = StoreInfo(
        backend="chroma",
        path=str(path),
        exists=True,
        count=int(collection.count()),
        metadata=dict(collection.metadata or {}),
    )
    if info.count == 0:
        return info

    # Dimension: the collection metadata is authoritative when present; older
    # collections (including the current dev one) do not have it, so inspect
    # one embedding instead.
    try:
        meta_dim = int(info.metadata.get("embedding_dim") or 0)
    except (TypeError, ValueError):
        meta_dim = 0
    if meta_dim:
        info.dim = meta_dim
    else:
        sample = collection.get(limit=1, include=["embeddings"])
        embeddings = sample.get("embeddings")
        if embeddings is not None and len(embeddings) > 0:
            info.dim = len(embeddings[0])

    # Pull ids + metadata once.  The collection is the same "chunks" collection
    # used by the Worker; summary pseudo-chunks are identified by id suffix.
    result = collection.get(include=["metadatas"])
    ids = result.get("ids") or []
    metadatas = result.get("metadatas") or []
    for index, chunk_id in enumerate(ids):
        chunk_id = str(chunk_id)
        metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
        book_id = str(metadata.get("book_id", ""))
        info.ids.append(chunk_id)
        if _record_is_summary(chunk_id):
            info.book_summary_ids.setdefault(book_id, []).append(chunk_id)
        else:
            info.book_ids.setdefault(book_id, []).append(chunk_id)
    return info


@dataclass
class TokenizerInfo:
    provider: str
    model: str
    limit: int | None = None
    limit_source: str = "unknown"
    tokenizer: Any | None = None
    tokenizer_path: str = ""
    config_max_length: int | None = None
    config_model_max_length: int | None = None
    dim: int | None = None
    size_gb: float | None = None
    description: str = ""

    def can_measure_coverage(self) -> bool:
        return self.tokenizer is not None and bool(self.limit)


def _valid_limit(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 < value <= 10**9 else None


def _fastembed_metadata(model: str) -> dict[str, Any] | None:
    try:
        from fastembed import TextEmbedding  # noqa: PLC0415

        for item in TextEmbedding.list_supported_models():
            if isinstance(item, dict) and item.get("model") == model:
                return item
    except Exception:
        pass
    return None


def _cache_dirs(model_path: str) -> list[Path]:
    candidates: list[Path] = []
    if model_path:
        candidates.append(resolve_data_path(model_path))
    candidates.extend(
        [
            ROOT / "data" / "models",
            Path.home() / ".cache" / "fastembed",
            Path.home() / ".cache" / "huggingface" / "hub",
        ]
    )
    # Preserve order, remove duplicates.
    seen: set[str] = set()
    result: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _find_tokenizer_file(model: str, model_path: str, metadata: dict[str, Any] | None) -> Path | None:
    base = Path(model_path).expanduser() if model_path else None
    if base and (base / "tokenizer.json").exists():
        return base / "tokenizer.json"

    hf_source = ""
    if metadata:
        hf_source = str((metadata.get("sources") or {}).get("hf") or "")

    patterns: list[str] = []
    for source in (hf_source, model):
        if source:
            patterns.append(f"models--{source.replace('/', '--')}/snapshots/*/tokenizer.json")

    for cache in _cache_dirs(model_path):
        if not cache.exists():
            continue
        for pattern in patterns:
            matches = sorted(cache.glob(pattern))
            if matches:
                return matches[-1]

    # Some fastembed versions use a flat "fast-<name>" cache directory.
    for cache in _cache_dirs(model_path):
        if not cache.exists():
            continue
        legacy = cache / f"fast-{model.split('/')[-1]}"
        if (legacy / "tokenizer.json").exists():
            return legacy / "tokenizer.json"

    # Last resort: if the configured cache has exactly one tokenizer, it is
    # almost certainly the configured model.  Do not guess when several
    # models are present.
    candidates: list[Path] = []
    for cache in _cache_dirs(model_path):
        if cache.exists():
            candidates.extend(cache.glob("models--*/snapshots/*/tokenizer.json"))
    unique = sorted({str(p) for p in candidates})
    if len(unique) == 1:
        return Path(unique[0])
    return None


def _read_tokenizer_config(tokenizer_path: Path) -> tuple[int | None, int | None]:
    config_path = tokenizer_path.with_name("tokenizer_config.json")
    if not config_path.exists():
        return None, None
    try:
        with config_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return None, None
    return _valid_limit(raw.get("max_length")), _valid_limit(raw.get("model_max_length"))


def _known_token_limit(model: str) -> int | None:
    lowered = model.lower()
    for name, limit in _KNOWN_TOKEN_LIMITS.items():
        if name in lowered:
            return limit
    return None


def _known_dimension(model: str) -> int | None:
    lowered = model.lower()
    for name, dim in _KNOWN_DIMENSIONS.items():
        if name in lowered:
            return dim
    return None


def tokenizer_info(cfg) -> TokenizerInfo:
    provider = cfg.embedding_provider
    model = cfg.active_embedder.model
    info = TokenizerInfo(provider=provider, model=model)

    if provider != "local":
        info.limit = _known_token_limit(model)
        info.dim = _known_dimension(model)
        if info.limit:
            info.limit_source = "known model limit (no local tokenizer)"
        return info

    metadata = _fastembed_metadata(model)
    if metadata:
        info.dim = metadata.get("dim")
        info.size_gb = metadata.get("size_in_GB")
        info.description = str(metadata.get("description") or "")
        description_match = re.search(r"(\d+)\s+input tokens truncation", info.description)
        if description_match:
            info.limit = int(description_match.group(1))
            info.limit_source = "fastembed model metadata"

    tokenizer_path = _find_tokenizer_file(model, cfg.embedding_local_model_path, metadata)
    if tokenizer_path is None:
        if info.limit is None:
            info.limit = _known_token_limit(model)
            if info.limit:
                info.limit_source = "known model limit"
        return info

    info.tokenizer_path = str(tokenizer_path)
    info.config_max_length, info.config_model_max_length = _read_tokenizer_config(tokenizer_path)
    config_limits = [
        limit for limit in (info.config_model_max_length, info.config_max_length) if limit is not None
    ]
    if config_limits:
        info.limit = min(config_limits)
        parts = []
        if info.config_max_length is not None:
            parts.append(f"max_length={info.config_max_length}")
        if info.config_model_max_length is not None:
            parts.append(f"model_max_length={info.config_model_max_length}")
        info.limit_source = "tokenizer_config.json (" + ", ".join(parts) + ")"
    elif info.limit is None:
        info.limit = _known_token_limit(model)
        if info.limit:
            info.limit_source = "known model limit"

    try:
        from tokenizers import Tokenizer  # noqa: PLC0415

        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        # The diagnostics count the *untruncated* encoding and then inspect
        # the first `limit` tokens, exactly like fastembed's ONNX preprocessor
        # when it applies the tokenizer's configured truncation.
        tokenizer.no_truncation()
        info.tokenizer = tokenizer
    except Exception as exc:  # pragma: no cover - depends on local cache
        info.description = (info.description + f" (tokenizer load failed: {exc})").strip()
    return info


def chunk_covered_chars(tokenizer: Any, text: str, limit: int) -> tuple[int, int]:
    """Return (characters covered by the first `limit` tokens, total tokens)."""
    encoding = tokenizer.encode(text)
    token_count = len(encoding.ids)
    limit = max(int(limit), 1)
    end = 0
    for index, (_, token_end) in enumerate(encoding.offsets):
        if index >= limit:
            break
        if token_end > end:
            end = token_end
    return min(end, len(text)), token_count


# Backwards-compatible private alias used inside this module.
_chunk_covered_chars = chunk_covered_chars


@dataclass
class CoverageResult:
    total_chars: int = 0
    covered_chars: int = 0
    total_chunks: int = 0
    over_limit_chunks: int = 0
    token_counts: list[int] = field(default_factory=list)
    chapters: list[dict[str, Any]] = field(default_factory=list)

    @property
    def coverage_pct(self) -> float:
        return (self.covered_chars / self.total_chars * 100.0) if self.total_chars else 0.0

    @property
    def over_limit_pct(self) -> float:
        return (self.over_limit_chunks / self.total_chunks * 100.0) if self.total_chunks else 0.0

    def token_stats(self) -> dict[str, int | None]:
        if not self.token_counts:
            return {"min": None, "median": None, "max": None}
        return {
            "min": min(self.token_counts),
            "median": int(statistics.median(self.token_counts)),
            "max": max(self.token_counts),
        }


def compute_coverage(
    con: sqlite3.Connection,
    tokenizer: TokenizerInfo,
    book_ids: Sequence[str] | None = None,
    include_chapters: bool = False,
) -> CoverageResult | None:
    """Measure how much *unique chapter text* the model can actually see.

    A chunk's stored text starts at the chunk's ``start_offset`` in its
    chapter.  We tokenize the chunk, find the last character offset among the
    first ``limit`` tokens, and mark that prefix in a per-chapter bitmap.  The
    union of all such prefixes is the text covered by at least one chunk
    embedding.  This avoids over-counting the configured chunk overlap between
    chunks and matches the coverage figures used in the earlier audit.
    """
    if not tokenizer.can_measure_coverage():
        return None

    assert tokenizer.tokenizer is not None and tokenizer.limit is not None
    tok = tokenizer.tokenizer
    limit = tokenizer.limit

    if book_ids is None:
        rows = con.execute("SELECT id, title FROM books ORDER BY title").fetchall()
        selected = [(row["id"], row["title"]) for row in rows]
    else:
        selected = []
        for book_id in book_ids:
            row = con.execute("SELECT id, title FROM books WHERE id = ?", (book_id,)).fetchone()
            if row is not None:
                selected.append((row["id"], row["title"]))

    result = CoverageResult()
    for book_id, book_title in selected:
        chapters = con.execute(
            "SELECT id, title, sort_order, content FROM chapters WHERE book_id = ? "
            "ORDER BY sort_order, id",
            (book_id,),
        ).fetchall()
        if not chapters:
            continue

        maps: dict[str, bytearray] = {}
        per_chapter: dict[str, dict[str, Any]] = {}
        for chapter in chapters:
            content = chapter["content"] or ""
            maps[chapter["id"]] = bytearray(len(content))
            per_chapter[chapter["id"]] = {
                "book_id": book_id,
                "book_title": book_title,
                "chapter_id": chapter["id"],
                "title": chapter["title"] or "",
                "sort_order": chapter["sort_order"],
                "total_chars": len(content),
                "covered_chars": 0,
                "chunks": 0,
                "over_limit_chunks": 0,
            }

        chunks = con.execute(
            "SELECT chapter_id, content, start_offset FROM chunks WHERE book_id = ? "
            "ORDER BY chapter_id, position",
            (book_id,),
        ).fetchall()
        for chunk in chunks:
            chapter_id = chunk["chapter_id"]
            content = chunk["content"] or ""
            covered, token_count = _chunk_covered_chars(tok, content, limit)
            chapter_map = maps.get(chapter_id)
            if chapter_map is None:
                continue

            start = max(int(chunk["start_offset"] or 0), 0)
            end = min(start + covered, len(chapter_map))
            if end > start:
                chapter_map[start:end] = b"\x01" * (end - start)

            chapter_stat = per_chapter[chapter_id]
            chapter_stat["chunks"] += 1
            if token_count > limit:
                chapter_stat["over_limit_chunks"] += 1
                result.over_limit_chunks += 1
            result.total_chunks += 1
            result.token_counts.append(token_count)

        for chapter in chapters:
            chapter_id = chapter["id"]
            content_len = len(chapter["content"] or "")
            covered = sum(maps[chapter_id])
            chapter_stat = per_chapter[chapter_id]
            chapter_stat["covered_chars"] = covered
            result.total_chars += content_len
            result.covered_chars += covered
            if include_chapters:
                result.chapters.append(chapter_stat)

    if include_chapters:
        result.chapters.sort(key=lambda item: (item["book_id"], item["sort_order"], item["title"]))
    return result


def fmt_int(value: int | None) -> str:
    return "-" if value is None else f"{int(value):,}"


def fmt_pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


def clip(text: Any, width: int) -> str:
    value = "" if text is None else str(text).replace("\n", " ").replace("\t", " ")
    if len(value) <= width:
        return value
    return value[: max(width - 1, 0)] + "…"


def print_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    right_align: set[int] | None = None,
    max_col_width: int = 48,
) -> None:
    right_align = right_align or set()
    rendered: list[list[str]] = []
    for row in rows:
        rendered.append([clip(cell, max_col_width) for cell in row])
    widths = [len(str(header)) for header in headers]
    for row in rendered:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    widths = [min(width, max_col_width) for width in widths]

    def line(values: Sequence[str]) -> str:
        cells = []
        for index, value in enumerate(values):
            value = clip(value, widths[index])
            cells.append(value.rjust(widths[index]) if index in right_align else value.ljust(widths[index]))
        return "  " + "  ".join(cells).rstrip()

    print(line(headers))
    print("  " + "  ".join("-" * width for width in widths))
    for row in rendered:
        print(line(row))


def dump_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
