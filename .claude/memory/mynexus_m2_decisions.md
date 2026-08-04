---
name: mynexus-m2-decisions
description: MyNexus M2 (book import/task processing) architecture decisions and where they diverge from the docs
metadata:
  type: project
---

M2 implements the upload → parse → chapters-stored → task-status-visible loop (docs/开发技术文档.md §10.3). Key decisions made while building it:

**Core API owns all DB writes; Worker is stateless and reports via HTTP callback.**
docs/系统设计文档.md §2.3's sequence diagram literally shows `SPLITTER -- "Chunk 元数据回写" --> RDBMS` (Worker writing directly to the shared SQLite file). That was deliberately not implemented that way — instead Worker POSTs progress/complete/fail callbacks to Core API (`/internal/tasks/{id}/{progress,complete,fail}`), and only Core API touches SQLite.
Why: avoids duplicating the schema/migration logic in two languages, avoids multi-process SQLite write contention on NAS hardware, keeps DB ownership in one place matching §1.2's "Core API 负责元数据 CRUD" framing.
How to apply: when M3 adds chunking/embedding, keep this pattern — Worker computes, Core API persists. If a future contributor points at §2.3's diagram literally, flag this documented divergence rather than "fixing" it back to direct writes.

**Callback URL is passed per-request, not statically configured on Worker.**
Core API's `config.Server.InternalURL` (e.g. `http://core-api:8080`) is sent as `callback_base_url` in every `/internal/ingest` request body, rather than Worker having its own static `core_api.url` config. Keeps the two services' configs from drifting out of sync.

**Original upload filename is threaded through as a title hint, not baked into the storage path.**
File is stored as `<uploadDir>/<bookID><ext>` (clean, no user-controlled string in the path). The original filename is sent separately as `original_filename` in the ingest request and only used by `TxtParser` as a title fallback (EPUB has real embedded metadata, so it ignores this hint). `BaseParser.process(file_path, display_name="")` signature reflects this.

**EPUB nav/TOC document must be excluded from chapter list.**
`ebooklib`'s spine can include the nav.xhtml/EpubNav item as ITEM_DOCUMENT type, which if not filtered gets parsed as a bogus first "chapter" (the table of contents itself). Fixed in `EpubParser.process` by skipping `isinstance(item, (epub.EpubNav, epub.EpubNcx))`.

**M2 explicitly does not include chunking/embedding** — despite docs/系统设计文档.md §3.3's `IngestionPipeline` pseudocode showing Parser→Cleaner→Splitter→Embedder together. 开发技术文档.md §10.3's M2 deliverables list stops at "章节与正文内容落库" (chapters/content stored); splitting+embedding is explicitly M3 scope (§10.4). `worker/src/pipelines/ingestion.py`'s `IngestionPipeline` currently only does parse+clean.

See [[mynexus_worker_cli_testable]] for the CLI-testability convention established while building this, and [[mynexus_macos_proxy_gotcha]] for a local dev environment trap hit during integration testing.
