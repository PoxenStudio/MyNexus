package service

import (
	"path/filepath"
	"testing"

	"mynexus/core-api/internal/storage/sqlite"
)

// Tool results must survive a history reload: the client re-renders visuals
// such as the mindmap card from the persisted frames, so a turn's
// generate_mindmap payload has to come back out of ListMessages intact.
func TestChatMessagesPersistToolResults(t *testing.T) {
	store, err := sqlite.Open(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatalf("open migrated database: %v", err)
	}
	defer store.Close()

	if _, err := store.DB().Exec(
		`INSERT INTO chat_sessions (id, user_id, title, book_ids) VALUES (?, ?, ?, ?)`,
		"session-1", "user-1", "标题", `["book-1"]`,
	); err != nil {
		t.Fatalf("insert session: %v", err)
	}

	chats := NewChatService(store.DB())
	toolResults := `[{"tool_name":"generate_mindmap","result_json":"{\"title\":\"导图\"}"}]`
	if err := chats.AppendMessage("session-1", "assistant", "答案", "[]", toolResults, "{}"); err != nil {
		t.Fatalf("append assistant message: %v", err)
	}
	if err := chats.AppendMessage("session-1", "user", "问题", "[]", "[]", "{}"); err != nil {
		t.Fatalf("append user message: %v", err)
	}

	messages, err := chats.ListMessages("session-1")
	if err != nil {
		t.Fatalf("list messages: %v", err)
	}
	if len(messages) != 2 {
		t.Fatalf("expected 2 messages, got %d", len(messages))
	}
	if messages[0].ToolResults != toolResults {
		t.Errorf("assistant tool_results = %q, want %q", messages[0].ToolResults, toolResults)
	}
	if messages[1].ToolResults != "[]" {
		t.Errorf("user tool_results = %q, want []", messages[1].ToolResults)
	}
}
