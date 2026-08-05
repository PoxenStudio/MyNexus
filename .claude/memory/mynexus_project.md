---
name: mynexus-project
description: MyNexus project shape — what it is, tech stack, milestone plan, and where things live
metadata:
  type: project
---

MyNexus is a private "book knowledge base" system: turns EPUB/PDF/TXT ebooks into a searchable, queryable, chat-able knowledge asset for the MyBooks/MyReader ecosystem. Repo: `/Volumes/data/projects/poxenstudio/MyNexus`.

Three services, Monorepo:
- `core-api/` — Go + Gin, owns all business data (SQLite via `modernc.org/sqlite`, pure-Go/no-CGO driver chosen deliberately for easy multi-arch NAS builds). Layered as `internal/{api/{handler,middleware,dto},service,storage,coordinator,models,config}`.
- `worker/` (renamed from `worker-ai` per user request) — Python + FastAPI, stateless capability node layer (parse/clean/split/embed/retrieve/LLM). Structured as `src/{nodes/{parsers,cleaners,splitters,embedders,llm},pipelines,vector_store,schemas}`.
- `web-ui/` — Vue 3 + TypeScript + Vite, calls Core API only.

Docs live in `docs/`: 需求文档.md (requirements), 系统设计文档.md (system design, authoritative for API paths — see [[mynexus_m2_decisions]]), 开发技术文档.md (dev/build-order plan, has the milestone definitions and acceptance criteria).

4 milestones (confirmed reasonable, not restructured):
- M1 project skeleton — done. Gin/FastAPI/Vue3 real skeletons, SQLite migrations, health checks.
- M2 book import & task processing — done. Upload → parse (EPUB/TXT) → chapters stored → task pending/processing/completed/failed lifecycle visible. See [[mynexus_m2_decisions]].
- M3 retrieval & QA — done. Chunking, embedding, ChromaDB vector store, hybrid (vector+BM25) search, streaming RAG chat with citations, chat session persistence. See [[mynexus_m3_decisions]].
- M4 admin backend & ops — done. Admin web-ui (dashboard/books/tasks/tokens), API Token issuance+validation, rate limiting, task retry, i18n (frontend). See [[mynexus_m4_decisions]] for scope boundaries and deferred items.

Dev loop: `make dev-up` / `make dev-down` (renamed from `m1-up`/`m1-down` per user request — no longer milestone-scoped, reused across all milestones). Runs all three services locally against `./config/config.yaml` and `./data/`.

Auth: `defaultUserID = "local-user"` is still hardcoded as the *resource owner* for books/tasks/tokens/chat sessions (single-tenant data model, unchanged) — but admin-backend *access* is no longer wide open: post-M4, a real session-based admin login was added (default `admin`/`admin`, change-password page), and `middleware.RequireAuth` now mandates either a valid session or a valid API token on every `/api/v1` route. See [[mynexus_admin_auth]] for the full auth/session/chat-toggle work and [[mynexus_m2_decisions]] for the original MyBooks-has-no-JWT reasoning that steered this toward Cookie/Session over JWT. Also added beyond M4: a real Postgres storage backend alongside SQLite ([[mynexus_postgres_backend]]), version-tracked schema migrations ([[mynexus_migration_versioning]]), and the end-user chat page inside the admin app gated by a new `chat.enabled` config toggle ([[mynexus_admin_auth]]). All 4 planned milestones are complete; everything in this paragraph is new scope built afterward, not milestone backlog.
