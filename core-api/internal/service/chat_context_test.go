package service

import (
	"path/filepath"
	"testing"

	"mynexus/core-api/internal/storage/sqlite"
)

const sampleContext = `{"reading":{"chapter_title":"第三章 巳正","section_index":3,"progress_fraction":0.42}}`

func newChatTestStore(t *testing.T) *ChatService {
	t.Helper()
	store, err := sqlite.Open(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatalf("open migrated database: %v", err)
	}
	t.Cleanup(func() { _ = store.Close() })
	if _, err := store.DB().Exec(
		`INSERT INTO chat_sessions (id, user_id, title, book_ids) VALUES (?, ?, ?, ?)`,
		"session-1", "user-1", "标题", `["book-1"]`,
	); err != nil {
		t.Fatalf("insert session: %v", err)
	}
	return NewChatService(store.DB())
}

func TestChatMessageContextRoundTrip(t *testing.T) {
	chats := newChatTestStore(t)
	if err := chats.AppendMessage("session-1", "user", "本章讲了什么", "[]", "[]", sampleContext); err != nil {
		t.Fatalf("append user message: %v", err)
	}

	messages, err := chats.ListMessages("session-1")
	if err != nil {
		t.Fatalf("list messages: %v", err)
	}
	if len(messages) != 1 {
		t.Fatalf("expected 1 message, got %d", len(messages))
	}
	if messages[0].ContextJSON != sampleContext {
		t.Errorf("context_json = %q, want %q", messages[0].ContextJSON, sampleContext)
	}
}

func TestChatMessageContextDefaultsToEmptyObject(t *testing.T) {
	chats := newChatTestStore(t)
	if err := chats.AppendMessage("session-1", "assistant", "答案", "[]", "[]", ""); err != nil {
		t.Fatalf("append assistant message: %v", err)
	}

	messages, err := chats.ListMessages("session-1")
	if err != nil {
		t.Fatalf("list messages: %v", err)
	}
	if messages[0].ContextJSON != "{}" {
		t.Errorf("empty context = %q, want {}", messages[0].ContextJSON)
	}
}

func TestChatMessageContextLegacyRowDefault(t *testing.T) {
	chats := newChatTestStore(t)
	if _, err := chats.db.Exec(
		`INSERT INTO chat_messages (id, session_id, role, content, citations, tool_results, created_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?)`,
		"legacy-1", "session-1", "user", "旧消息", "[]", "[]", "2024-01-01T00:00:00Z",
	); err != nil {
		t.Fatalf("insert legacy message: %v", err)
	}

	messages, err := chats.ListMessages("session-1")
	if err != nil {
		t.Fatalf("list messages: %v", err)
	}
	if messages[0].ContextJSON != "{}" {
		t.Errorf("legacy context = %q, want {}", messages[0].ContextJSON)
	}
}

func TestBuildChatPromptCarriesMessageContext(t *testing.T) {
	chats := newChatTestStore(t)
	if err := chats.AppendMessage("session-1", "user", "本章讲了什么", "[]", "[]", sampleContext); err != nil {
		t.Fatalf("append user message: %v", err)
	}
	if err := chats.AppendMessage("session-1", "assistant", "答案", "[]", "[]", ""); err != nil {
		t.Fatalf("append assistant message: %v", err)
	}

	prompt, err := chats.BuildChatPrompt("session-1", 10)
	if err != nil {
		t.Fatalf("build chat prompt: %v", err)
	}
	if len(prompt.Messages) != 2 {
		t.Fatalf("expected 2 prompt messages, got %d", len(prompt.Messages))
	}
	if prompt.Messages[0].ContextJSON != sampleContext {
		t.Errorf("user context = %q, want %q", prompt.Messages[0].ContextJSON, sampleContext)
	}
	if prompt.Messages[1].ContextJSON != "{}" {
		t.Errorf("assistant context = %q, want {}", prompt.Messages[1].ContextJSON)
	}
}
