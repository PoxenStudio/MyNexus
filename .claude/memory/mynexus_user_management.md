---
name: mynexus-user-management
description: "MyNexus multi-user support — admin_users renamed to users, role-based (admin/user) access, user-management admin page"
metadata: 
  node_type: memory
  type: project
  originSessionId: 377214c9-e542-4e80-b66b-78d185bf94ef
  modified: 2026-08-06T13:35:51.318Z
---

Extended the single-admin login system ([[mynexus_admin_auth]]) into real multi-user support with two roles, on 2026-08-06.

**Table renamed `admin_users` → `users`, plus new columns.** New migration `0007_user_roles.sql` (sqlite) / `0008_user_roles.sql` (postgres): `ALTER TABLE admin_users RENAME TO users`, then adds `nickname`, `role` ('admin'|'user', default 'admin'), `status` ('active'|'disabled', default 'active'), `last_login_at`. Existing seeded admin account becomes `role=admin` automatically via the column default — no backfill needed. Go-side renamed to match: `models.User` (was `AdminUser`), `service.UserService` (was `AdminUserService`, still owns `EnsureDefaultAdmin`/`DefaultAdminUsername`/`DefaultAdminPassword`), `handler.UserHandler` is new (the admin-only CRUD surface), `handler.AuthHandler` unchanged in shape but now takes a `*UserService`.

**Role travels with the session, not looked up per-request.** `auth.SessionManager.Create/Validate` now carry `role` alongside `userID`/`username` — same in-memory, no-DB-lookup design as before. Consequence: role changes and disable/enable only take effect on next login or when the 24h session expires, not instantly on an already-logged-in browser tab. Deliberate tradeoff (asked and confirmed), documented here rather than re-litigated: instant revocation would mean a DB query on every authenticated request.

**`middleware.RequireAdmin`** (new, in `middleware/auth.go`) gates the back-office route group — books/tasks/tokens/audit-log/system/settings/users — behind `role == "admin"`. Chat and the two self-service `/auth/*` routes (change-password, avatar) stay open to both roles. API-token auth (`Authorization: Bearer mnx_...`) is always treated as admin-equivalent (`c.Set("role", "admin")`) since Tokens are an admin/automation concern.

**Guardrails against locking yourself out**, enforced in `service.UserService`: `SetRole`/`SetStatus` refuse to demote/disable the *last* active admin (`ErrLastAdmin`), and `handler.UserHandler` additionally refuses to let the caller change their *own* role or disable their *own* account (`admin_user_id` from context vs the `:id` param) — belt-and-suspenders, the last-admin check alone wouldn't stop a 2-admin shop from disabling themselves while another admin exists.

**Frontend gating mirrors the backend.** `router/index.ts` routes get `meta.requiresAdmin`; the global `beforeEach` bounces a non-admin to `/chat` (its only other page). `stores/auth.ts` gained `role`/`isAdmin`; login redirect and the "already logged in, visiting /login" redirect both branch on `auth.isAdmin` (dashboard vs chat) instead of always going to dashboard. `AppLayout.vue`'s `navItems` and `settingsChildren` are filtered by role — a "user" account only ever sees Chat + 个人信息 (own password/avatar, still `AdminAccountView.vue`/`/settings/account`, name kept for URL stability though the i18n label changed from "管理员账号" to "个人信息"/"My Profile" since both roles land there now).

**New admin page**: `web-ui/src/views/admin/UsersView.vue` (`/settings/users`) — list with inline role `<select>` and status toggle, "新增用户" dialog, per-row "重置密码" dialog. Self-row's role select and disable button are hidden/disabled client-side too (UX only; server is the real enforcement). Backend routes: `GET/POST /api/v1/users`, `PUT /api/v1/users/:id/{role,status,password}`.

**Verified via curl smoke test** (admin login → create `alice`/role=user → alice hits admin-only route → 403 → alice self-service change-password → 204 → admin disables alice → alice re-login → 401 → admin tries to disable/demote self → 400 both times → admin resets alice's password → 204). All passed.

**Follow-up (2026-08-06): chat sessions were NOT actually per-user despite `chat_sessions.user_id` existing.** `ChatHandler` was still writing/reading every session under the pre-auth placeholder `defaultUserID` ("local-user", from `book_handler.go` — a leftover from before real auth existed, still correctly used for the admin-only books/tasks/tokens handlers, but wrong for chat once "user" role accounts could reach it). Fixed: `Completions`/`ListSessions` now use `c.GetString("user_id")` (set by `RequireAuth`); `GetSession`/`RenameSession`/`DeleteSession`, and `Completions` when handed an existing `session_id`, all go through a new `sessionOwnedBy(sessionID, userID)` check first — cross-user access returns a plain 404 ("session not found"), not 403, so a guessed/leaked ID doesn't confirm another user's session exists. Verified via curl: bob and carol (both role=user) each only see their own sessions; bob's GET/DELETE/piggyback-via-completions against carol's session_id all 404 and leave her session untouched.

**Added `config.ChatConfig.MaxSessions`** (yaml/json `max_sessions`, default 100) — per-user cap enforced by `ChatService.EnforceSessionLimit(userID, max)`, called right after each new session is created (not before — a session in progress is never blocked mid-cap). Over the cap = **prune oldest by `updated_at`, silently** (single query with `... WHERE user_id = ? AND id NOT IN (SELECT ... ORDER BY updated_at DESC LIMIT ?)`, applied to `chat_messages` first then `chat_sessions`), not a hard error — a user just quietly loses their oldest idle conversation rather than getting blocked from starting a new chat. Surfaced in the admin "系统配置 > 基础设置" page (`SystemConfigView.vue`) right under the chat-enabled toggle, round-trips through the existing `GET/PUT /system/settings` (`dto.SystemSettings.Chat` already covered the whole `ChatConfig` struct, no DTO change needed). Verified with `max_sessions: 3`: 5 created sessions for one user pruned down to exactly 3 (newest kept), a second user's 1 session unaffected.

**Free fix while touching `DeleteSession`**: it now explicitly deletes `chat_messages` before the `chat_sessions` row, instead of relying on the schema's `ON DELETE CASCADE`. That FK is a no-op under sqlite unless a connection opts in via `PRAGMA foreign_keys=ON` — `storage/sqlite/sqlite.go`'s `Open()` doesn't set it — so session deletes (including the new pruning path) were silently orphaning `chat_messages` rows on sqlite before this. Postgres was never affected (it enforces FKs unconditionally), but the fix makes both backends behave identically either way.

**Not done / open questions:**
- No immediate session revocation on disable/role-change (see above) — acceptable given 24h TTL, but worth knowing if a "kick this user right now" requirement shows up later.
- No password-complexity policy beyond length ≥ 4 (same bar as the original single-admin `ChangePassword`) — deliberately unchanged, not evaluated as a gap for this pass.
- No audit-log UI filtering by new `user.*` action types (`user.create`, `user.set_role`, `user.set_status`, `user.reset_password`) — they show up in the existing audit log table fine, just no special treatment.
