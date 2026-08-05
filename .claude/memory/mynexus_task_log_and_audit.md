---
name: mynexus-task-log-and-audit
description: Task stages_log now actually populated per-stage, and a new admin_audit_log table/page tracking admin actions
metadata:
  type: project
---

Two related "visibility" gaps closed in the same session: structured per-task processing logs, and an admin operation audit trail.

**`tasks.stages_log` was already wired on the Worker side but silently dropped on Core API's.** `worker/src/pipelines/ingestion.py`'s `_report_progress()` had been sending `{progress, stage, message}` (stage names like `"parsing"`, `"cleaning_done"`, `"splitting_done"`, `"embedding"`) to `/internal/tasks/{id}/progress` since M2/M3, and `dto.TaskProgressCallback` already had the `Stage`/`Message` fields — but `TaskService.UpdateProgress(id, progress)` only took the bare progress int and threw the rest away. Fixed by rewriting `task_service.go`: `transition()` + `appendStageLog()` now read-modify-write the `stages_log` JSON array on every progress/complete/fail/retry call, appending `{stage, message, progress, at}` rather than overwriting. `models.StageLogEntry` is the new struct; `dto.TaskResponse` now returns `stages_log` as a parsed array (was previously omitted from the response entirely). `web-ui`'s Tasks page: click a row to expand a timeline of stage entries.
No transaction/locking around the read-modify-write — acceptable because `worker.max_concurrent_tasks: 1` means only one task is ever being progressed at a time in this architecture; don't assume this is safe if that constraint changes.

**New `admin_audit_log` table + page**, resolving 需求文档.md §6.7.3's "操作审计记录" gap. `AuditService.Log(actor, action, targetType, targetID, detail)` / `.List(page, size)`; new migration `0003_admin_audit_log.sql` (both sqlite/postgres, see [[mynexus_migration_versioning]] for why schema changes are new files now). `GET /api/v1/audit-log` (protected route, same session-or-token gate as everything else) + `web-ui/src/views/admin/AuditLogView.vue` + nav entry.

**Actor labeling comes from `middleware.RequireAuth`, not a second lookup.** `RequireAuth` already resolves *who* made the request while validating auth — extended it to also set `c.Set("actor", ...)`: the admin's username for session auth (added `username` to `auth.SessionManager`'s stored session struct so `Login` can pass it straight through without a DB round-trip), or `"token:<alias>"` for API Token auth (extended `TokenService.Authenticate` to also return the token's alias, its only caller being this middleware). Handlers that want to audit-log an action just do `actor, _ := c.Get("actor")` — no new DB query needed at the call site.

**What's actually logged**: `auth.login` / `auth.login_failed` (failed attempts logged under the *typed* username, not a resolved actor, since auth didn't succeed), `auth.logout`, `auth.change_password`, `book.delete`, `task.retry`, `token.create`, `token.revoke`. Deliberately did NOT log read-only actions (list/get) — audit logs are for state-changing admin actions, per the 需求文档 wording ("操作审计记录", i.e. operations, not views). If a future ask wants read access logged too (e.g. for compliance), that's a different scope.

**Verified**: curl end-to-end (login → create token → revoke token → change password → `GET /audit-log` shows all four in order with correct actor/action/target); stage log verified by hand-inserting a task row via `sqlite3` and hitting `/internal/tasks/{id}/progress` and `/fail` directly (no live Worker needed) — confirmed entries append rather than overwrite, and survive through to the authenticated `GET /api/v1/tasks/{id}` response. Also re-verified through the real Vite dev-proxy path, not just direct-to-Core-API curl.
