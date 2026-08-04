---
name: mynexus-worker-cli-testable
description: User wants every MyNexus worker pipeline node individually runnable from the command line
metadata:
  type: feedback
---

Every Worker capability node (parser, cleaner, and — going forward — splitter/embedder/llm) must support being run standalone from the command line, not only through the FastAPI server.

Why: the user said explicitly "每个任务都需要支持可单独在命令行下运行 后续这种单独测试会很多" (each task needs to support running standalone on the command line, there will be a lot of this kind of individual testing going forward). Parsing/splitting/embedding quality varies a lot per input file, so quick manual CLI checks without spinning up the whole stack are expected to be a recurring workflow.

How to apply: every new node module under `worker/src/nodes/**` and every pipeline under `worker/src/pipelines/**` gets an `if __name__ == "__main__":` block with `argparse`, invoked as:
```
cd worker/src && python3 -m nodes.parsers.epub_parser path/to/book.epub
cd worker/src && python3 -m pipelines.ingestion path/to/book.epub   # dry-run, no Core API/HTTP involved
```
This works because imports are absolute relative to `worker/src` (no `__init__.py` files, namespace packages) — running with `-m` from that directory puts it on `sys.path`. Do NOT run these files directly with `python3 path/to/file.py`, it breaks the `from nodes.x import y` style absolute imports.

Established in M2 for `epub_parser.py`, `txt_parser.py`, `whitespace_cleaner.py`, and `pipelines/ingestion.py` (which exposes a pure `parse_and_clean()` with no HTTP side effects, separate from `run()` which does the HTTP callbacks — this split is what makes the dry-run CLI mode possible). Keep this same split (pure-logic method + thin HTTP-wrapping method) for M3's splitter/embedder/retrieval/LLM nodes so they stay CLI-testable too.
