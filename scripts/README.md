# Embedding diagnostics scripts

These scripts inspect the embedding model, the Chroma/SQLite vector store and
the chunk table using the same `config/config.yaml` as the Worker. The info
scripts are read-only: SQLite is opened with `mode=ro`, and the Chroma
collection is read without creating it. The recall script uses the Worker's
normal vector-store factory (it opens/creates the collection) but never writes
vectors.

Run them from the repository root (or pass absolute `--config`, `--db` and
`--vectorstore` paths). The host Python needs the Worker dependencies
(`chromadb`, `fastembed`, `tokenizers`, `jieba`, ...).

## Global information

```bash
python3 scripts/embedding_info.py
python3 scripts/embedding_info.py --json
```

Shows the configured embedding provider/model, dimension, token limit, vector
store path/count/dimension, DB counts, token-limit overflow, unique chapter
coverage and per-book vector counts.

`--no-coverage` skips tokenizing every chunk when you only need counts.

## One book

```bash
python3 scripts/book_embedding_info.py <book-id>
python3 scripts/book_embedding_info.py <book-id> --chapters
python3 scripts/book_embedding_info.py <book-id> --json
```

Shows the book's chapter/chunk/character counts, content and summary vectors,
missing/orphan vectors, token overflow, unique chapter coverage and — with
`--chapters` — per-chapter statistics. Use `embedding_info.py` to list book
ids and titles.

## Recall test

The earlier audit (with 500-character chunks) found that the local MiniLM model
only encodes the first 128 tokens of each chunk. This script makes that
experiment repeatable:

```bash
# 20 tail queries, balanced across all books, vector retrieval
python3 scripts/embedding_recall_test.py --samples 20

# one book, 10 tail queries per book, compare vector and hybrid retrieval
python3 scripts/embedding_recall_test.py \
  --book-id <book-id> --samples-per-book 10 --mode both

# test a different part of each chunk
python3 scripts/embedding_recall_test.py --query-source head
python3 scripts/embedding_recall_test.py --query-source random

# search all selected books instead of only the source chunk's book
python3 scripts/embedding_recall_test.py --samples 30 --scope selection
```

Key options:

| Option | Meaning |
| --- | --- |
| `--samples N` | total samples, distributed round-robin across books |
| `--samples-per-book N` | instead of `--samples`, take N from each book |
| `--query-source tail\|head\|random\|both` | where the query text comes from |
| `--mode vector\|hybrid\|both` | compare vector-only with BM25 fusion |
| `--scope book\|selection\|all` | restrict each search to the source book, selected books, or all books |
| `--top-k N` | largest cut-off in the report (default 30) |
| `--seed N` | deterministic sampling/query selection |
| `--json` | machine-readable output |

For `tail`, the query is taken from the part of the chunk *after* the model's
first `token_limit` tokens. If the model has no truncation (for example a
long-context model), there is no unseen tail; use `--query-source head` or
`--query-source random` instead. When the provider has no local tokenizer, the
script falls back to the last `--tail-fraction` (default 25%) of the chunk and
prints a note.

Metrics are `hit@1`, `hit@5`, `hit@10`, `hit@top_k` and MRR. A rank of `0`
means the source chunk was not found in the searched scope.

## Notes on the numbers

- `chunks.token_count` may be written with a different tokenizer (for example
  the LLM tokenizer used by the splitter). The scripts re-tokenize chunk text
  with the **embedding model's** tokenizer and report those counts.
- `unique chapter coverage` is the union of characters covered by the first
  `token_limit` tokens of each chunk, mapped back to chapter offsets. It avoids
  counting the configured chunk overlap twice.
- `summary vectors` are the `*:summary` pseudo-chunks produced by the summary
  pipeline; they are excluded from content-vector integrity checks.
- Postgres-backed deployments are not supported by these scripts because they
  read `start_offset`/`end_offset` from SQLite directly.
