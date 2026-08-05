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

Auth: `defaultUserID = "local-user"` is still hardcoded everywhere (book_handler.go / chat_handler.go / token_handler.go) — M4 added real API Token *validation* (`middleware.APITokenAuth`, rejects invalid/revoked tokens) but did NOT make auth mandatory, since there's still no login flow for the admin UI to obtain a token with. See [[mynexus_m2_decisions]] for the original MyBooks-has-no-JWT reasoning and [[mynexus_m4_decisions]] for the enforcement decision. All 4 planned milestones are now complete; anything beyond this is new scope, not milestone backlog.
