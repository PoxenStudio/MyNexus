-- Mirrors storage/sqlite/migrations/0009_task_dispatch_queue.sql — see that
-- file for the full rationale.

ALTER TABLE tasks ADD COLUMN dispatched_at TIMESTAMP;
