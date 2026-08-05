---
name: mynexus-m4-decisions
description: MyNexus M4 (admin backend/ops) scope decisions — what shipped, what was deliberately deferred
metadata:
  type: project
---

M4 implements the admin backend, API Token management, and basic ops hardening (docs/开发技术文档.md §10.5). Scope decisions:

**Auth is enforced-when-present, not required.** `middleware.APITokenAuth` validates `Authorization: Bearer mnx_...` against `api_tokens` when the header is given (rejects invalid/revoked with 401), but requests with no `Authorization` header at all still pass through as `defaultUserID = "local-user"`. This is a deliberate continuation of the M1/M2 decision ([[mynexus_m2_decisions]]) to defer real user login: the admin web-ui has no login page, so hard-requiring a token on every route would lock admins out of their own UI. Real enforcement (a login flow issuing session/JWT, or requiring an API Token on all `/api/v1` routes) is still open — whoever adds a login page should also flip this to reject missing tokens.

**Rate limiting is in-process, per-IP, no Redis.** `middleware.RateLimit(20, 40)` — 20 req/s refill, burst 40 — is a plain in-memory token bucket keyed by `c.ClientIP()`. No external dependency, consistent with the single-process-per-NAS deployment model; resets on restart and doesn't share state across multiple Core API replicas (there are none in this architecture, so that's fine).

**API Token's "last 4 characters shown" required a schema change.** The design only ever stores `token_hash` (SHA-256), so there's no way to recover the real last-4 of the raw token from the hash for display. Added a `token_suffix` column to the `api_tokens` table (captured at creation time, before the raw token is discarded) — see `migrations/0001_init.sql`. At the time this was edited directly into the original migration file rather than added as a new numbered one, since migrations had no applied-tracking yet and no real deployments existed to preserve. **Superseded by [[mynexus_migration_versioning]]**: migrations are now tracked in a `schema_migrations` table, so any *future* schema change (including anything like this token_suffix column, if it happened today) should be a new numbered file, not an edit to an already-shipped one.

**Dashboard charts are hand-rolled inline SVG/CSS, not a charting library.** `components/charts/BarChart.vue` is ~40 lines of CSS width-percentage bars, no echarts/chart.js. Consistent with the dependency-weight scrutiny this session already applied to chromadb ([[mynexus_m3_decisions]]) — a full charting library is unjustified for "book count by status" and "task count by status" bar charts. `GET /api/v1/system/stats` was extended to return `books_by_status`/`tasks_by_status` maps plus totals to feed it, added per the user's new requirement (需求文档.md §6.7.2 "管理后台首页上方需要提供一组图表信息的看板").

**Frontend i18n shipped; backend i18n did not.** `web-ui` has real `vue-i18n` with zh-CN/zh-TW/en-US message files and a locale switcher (persisted to localStorage, falls back to `navigator.language`). Core API's error responses are still raw Go error strings in whatever language they were written in (English/mixed) — docs/系统设计文档.md §9.2's "Accept-Language 驱动的后端错误文案" was not implemented. Gap, not an oversight — flag it if a future task needs translated API error messages.

**Known gaps left for later** (none block M4's 开发技术文档.md acceptance criteria — "查看书籍列表/任务状态/处理日志", "创建/查看/吊销 Token", "NAS 环境稳定运行" — all met):
- No bulk book selection/bulk delete/bulk rebuild (需求文档 §6.7.3).
- No `POST /books/{id}/rebuild` endpoint (re-run parse/split/embed for an already-ingested book) — only failed-task retry (`POST /tasks/{id}/retry`, which just re-triggers ingest on the same file) exists.
- "处理日志" is currently just `tasks.error_msg` surfaced in the Tasks table — the `tasks.stages_log` column exists in the schema but nothing writes structured per-stage log entries into it.
- No chat/QA page in web-ui — M1-M4 all focused on the admin backend; the requirements doc's §6.7.1 "用户前端页面" (end-user chat UI) was never in any milestone's explicit deliverable list, so it's still entirely unbuilt.
- No audit log for admin actions (需求文档 §6.7.3 "操作审计记录").
- No virus/file-legitimacy scanning on upload (需求文档 §6.6, explicitly marked optional there too).
