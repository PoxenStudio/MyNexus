ALTER TABLE chat_sessions ADD COLUMN memory_summary TEXT NOT NULL DEFAULT '';
ALTER TABLE chat_sessions ADD COLUMN memory_updated_at TIMESTAMP;
ALTER TABLE chat_sessions ADD COLUMN memory_message_count INTEGER NOT NULL DEFAULT 0;
