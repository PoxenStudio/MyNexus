---
name: mynexus-bulk-book-ops
description: Single-book rebuild endpoint plus bulk delete/rebuild for the books admin page
metadata:
  type: project
---

Implements 需求文档.md §6.7.3's "批量选择书籍并执行删除或重建操作" and "对单本书籍执行重新构建" — resolves two previously-tracked gaps ([[mynexus_known_gaps_and_conflicts]]) in one pass, since bulk rebuild needs single-book rebuild as its building block anyway.

**`POST /books/{id}/rebuild` is not the same as `POST /tasks/{id}/retry`.** Retry (existing, M4) only applies to an already-failed task and reuses that task's row. Rebuild (`book_handler.go`'s `rebuildOne`) works on *any* book regardless of current status — including an already-`ready` one — by creating a brand-new task and re-submitting the book's existing stored file to Worker. Use case: re-processing after changing the embedding model, chunk size, or vector store config, not just recovering from a failure.

**Bulk endpoints process each ID independently and never abort early.** `POST /books/bulk-delete` / `POST /books/bulk-rebuild` (body `{"ids": [...]}`) loop over every ID, catching each one's error individually, and return `{"items": [{"id", "ok", "error"?}]}` — one bad ID (already deleted, no stored file, Worker unreachable) doesn't block the rest of the batch. The frontend (`BooksListView.vue`) surfaces failed items in a list under the bulk action bar rather than a single opaque error.

**Both single-rebuild and both bulk endpoints are audit-logged** (`book.rebuild`, `book.bulk_delete`, `book.bulk_rebuild`, alongside the existing `book.delete`) — see [[mynexus_task_log_and_audit]] for how actor labeling works. Bulk actions log once per batch (with the full ID list as `detail`, comma-joined), not once per item — keeps the audit log from being spammed by a 50-book bulk delete.

**Route registration note**: `/books/bulk-delete` and `/books/bulk-rebuild` are static POST siblings of `/books/import` (all under `/books`), and `/books/:id/rebuild` is a new 3-segment path — none of these collided with gin's radix-tree route matching (static routes take priority over `:id` wildcards at the same segment depth in gin v1.12). Verified by booting the server and confirming no route-registration panic, then hitting each endpoint with curl.

**Verified**: curl end-to-end including failure paths — bulk rebuild against 3 books (2 with files but Worker not running → correctly reported "failed to trigger ingestion" per-item; 1 with no stored file → correctly reported "book has no stored file to rebuild from"); bulk delete of 2 valid + 1 nonexistent ID → 2 succeeded, 1 reported `sql: no rows in result set`; confirmed only the 2 valid ones were actually removed from the `books` table afterward. Also re-verified through the real Vite dev-proxy path (initial 404s during that check turned out to be stale `mynexus-api` processes left running on port 8080 from earlier tests in the same session, not a real routing bug — killed them and reran clean).
