-- Tracks whether a task has actually been handed to Worker yet, distinct
-- from status='pending' (which now also covers "queued, waiting for a free
-- concurrency slot" — see internal/dispatch.Dispatcher). NULL means still
-- queued. Once set, the task counts against worker.max_concurrent_tasks
-- until it reaches a terminal status (completed/failed) — see
-- TaskService.CountDispatched/NextQueued/MarkDispatched.
ALTER TABLE tasks ADD COLUMN dispatched_at DATETIME;
