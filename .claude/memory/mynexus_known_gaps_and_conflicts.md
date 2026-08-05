---
name: mynexus-known-gaps-and-conflicts
description: Consolidated audit of unfinished work and design-doc-vs-implementation conflicts across MyNexus, as of M4 completion
metadata:
  type: project
---

Consolidated from [[mynexus_m2_decisions]], [[mynexus_m3_decisions]], [[mynexus_m4_decisions]] plus a fresh code check, per user request to summarize unfinished work / conflicts with the original design in one place.

## Design-doc vs. implementation conflicts (deliberate divergences)

1. **Worker never writes to SQLite directly**, despite 系统设计文档.md §2.3's sequence diagram showing `SPLITTER -- "Chunk 元数据回写" --> RDBMS`. Actual: Worker computes, POSTs callbacks to Core API (`/internal/tasks/{id}/...`), only Core API touches SQLite. See [[mynexus_m2_decisions]]. Documented divergence, not a bug.
2. ~~`storage.database: postgres` is not implemented.~~ **Resolved 2026-08-05** — see [[mynexus_postgres_backend]]. Both `sqlite` and `postgres` are now real, switchable backends.
3. **`auth.jwt_secret` config field exists but is dead code.** `config.Auth.JWTSecret` is parsed from `config.yaml`/env but never read anywhere else in `core-api` — there is no JWT signing, verification, or login endpoint. 系统设计文档.md's original assumption (JWT shared with MyBooks) was already corrected earlier this project (MyBooks actually uses Cookie/Session), but the leftover `jwt_secret` field in config was never removed even though nothing consumes it.
4. ~~No login flow exists, `middleware.APITokenAuth` is enforced-when-present rather than mandatory.~~ **Resolved 2026-08-05** — see [[mynexus_admin_auth]]. Real session-based admin login now exists; `middleware.RequireAuth` mandates either a valid session or a valid API token on every `/api/v1` route (except login/logout themselves).
5. **系统设计文档.md §9.2's "Accept-Language 驱动的后端错误文案" was not implemented.** Only `web-ui` has i18n (vue-i18n, 3 locales); Core API error strings are raw Go/English regardless of client locale.

## Unfinished / deferred work (not blocking any milestone's stated acceptance criteria, but real gaps)

- **No `POST /books/{id}/rebuild`** — can't re-run parse/split/embed for an already-ingested book. Only `POST /tasks/{id}/retry` exists, which just re-triggers ingest on the same stored file after a *failure*; there's no "force re-process a successfully completed book" path (e.g. after changing chunk size or embedding model).
- ~~`tasks.stages_log` column is written but never populated with real content~~ **Resolved 2026-08-05** — see [[mynexus_task_log_and_audit]].
- **No bulk book operations** (multi-select delete/rebuild) — 需求文档.md §6.7.3 asks for this, web-ui only supports single-book actions.
- ~~No admin action audit log~~ **Resolved 2026-08-05** — see [[mynexus_task_log_and_audit]].
- ~~No end-user chat/QA page~~ **Resolved 2026-08-05** — see [[mynexus_admin_auth]]. `web-ui/src/views/ChatView.vue` now exists, gated by `config.chat.enabled` and by admin login (it lives inside the authenticated admin app, not as a separate anonymous public page).
- **No upload virus/file-legitimacy scanning** — 需求文档.md §6.6 marks this optional; still skipped.
- **Hybrid search's BM25 side doesn't scale to a very large whole-library search** — `RetrievalPipeline` reloads the full keyword candidate set and rebuilds a `rank_bm25` index per query. Fine at current scale; would need Core API-side SQLite FTS5 (or similar) before a 50k-book library makes this the new bottleneck (the vector side no longer has this problem after the ChromaDB fix — see [[mynexus_m3_decisions]]).
- **Token/chunk-size accounting is a character-count approximation**, not a real tokenizer (`token_splitter.py`, `CHARS_PER_TOKEN = 1.0`) — fine for CJK, over-counts for English text; no `tiktoken` dependency by design.
- **CJK tokenization for BM25 is a crude regex**, not a real segmenter (no jieba) — each CJK character counted as its own token.

## Why this matters
When a future task touches auth, config, or the database layer, check this file first — several fields/interfaces in the codebase (`jwt_secret`, `database: postgres`) look implemented but are placeholders. Don't assume config surface area equals working functionality.
