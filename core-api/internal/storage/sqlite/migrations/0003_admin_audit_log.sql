-- Admin operation audit log (需求文档.md §6.7.3 "操作审计记录"). Records
-- who did what to which resource, for actions taken through the admin web-ui
-- or a service API Token — see AuditService.Log and its call sites.

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id          TEXT PRIMARY KEY,
    actor       TEXT NOT NULL,       -- admin username, or "token:<alias>" for API Token access
    action      TEXT NOT NULL,       -- e.g. "book.delete", "task.retry", "token.create"
    target_type TEXT DEFAULT '',
    target_id   TEXT DEFAULT '',
    detail      TEXT DEFAULT '',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON admin_audit_log(created_at);
