package service

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"mynexus/core-api/internal/models"
)

type ChatService struct {
	db *sql.DB
}

func NewChatService(db *sql.DB) *ChatService {
	return &ChatService{db: db}
}

func (s *ChatService) CreateSession(userID, bookIDsJSON string) (*models.ChatSession, error) {
	now := time.Now().UTC().Format(time.RFC3339)
	session := &models.ChatSession{
		ID: uuid.NewString(), UserID: userID, BookIDs: bookIDsJSON, CreatedAt: now, UpdatedAt: now,
	}
	_, err := s.db.Exec(
		`INSERT INTO chat_sessions (id, user_id, title, book_ids, created_at, updated_at) VALUES (?, ?, '', ?, ?, ?)`,
		session.ID, session.UserID, session.BookIDs, session.CreatedAt, session.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("insert chat session: %w", err)
	}
	return session, nil
}

func (s *ChatService) GetSession(id string) (*models.ChatSession, error) {
	row := s.db.QueryRow(
		`SELECT id, user_id, title, book_ids, created_at, updated_at FROM chat_sessions WHERE id = ?`, id)
	var sess models.ChatSession
	err := row.Scan(&sess.ID, &sess.UserID, &sess.Title, &sess.BookIDs, &sess.CreatedAt, &sess.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, err
	}
	if err != nil {
		return nil, fmt.Errorf("scan chat session: %w", err)
	}
	return &sess, nil
}

func (s *ChatService) ListSessions(userID string) ([]models.ChatSession, error) {
	rows, err := s.db.Query(
		`SELECT id, user_id, title, book_ids, created_at, updated_at
		 FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC`, userID)
	if err != nil {
		return nil, fmt.Errorf("list chat sessions: %w", err)
	}
	defer rows.Close()

	var sessions []models.ChatSession
	for rows.Next() {
		var sess models.ChatSession
		if err := rows.Scan(&sess.ID, &sess.UserID, &sess.Title, &sess.BookIDs, &sess.CreatedAt, &sess.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan chat session: %w", err)
		}
		sessions = append(sessions, sess)
	}
	return sessions, rows.Err()
}

// DeleteSession removes a session and its messages. Deletes chat_messages
// explicitly rather than relying on the schema's ON DELETE CASCADE — sqlite
// only enforces foreign keys when a connection opts in via PRAGMA (this
// project's sqlite.Open doesn't), so the cascade is a no-op there; deleting
// both rows here keeps behavior identical across sqlite and postgres.
func (s *ChatService) DeleteSession(id string) error {
	if _, err := s.db.Exec(`DELETE FROM chat_messages WHERE session_id = ?`, id); err != nil {
		return fmt.Errorf("delete chat messages: %w", err)
	}
	_, err := s.db.Exec(`DELETE FROM chat_sessions WHERE id = ?`, id)
	return err
}

// EnforceSessionLimit keeps at most maxSessions sessions for userID, deleting
// the oldest (by updated_at) once the count is exceeded. Called right after
// CreateSession — see config.ChatConfig.MaxSessions (admin-configurable,
// default 100, in "系统配置 > 基础设置"). <= 0 means no limit. Sessions are
// pruned, not blocked: a user hitting the cap just quietly loses their
// oldest conversation rather than getting an error on their next chat.
func (s *ChatService) EnforceSessionLimit(userID string, maxSessions int) error {
	if maxSessions <= 0 {
		return nil
	}
	_, err := s.db.Exec(`
		DELETE FROM chat_messages WHERE session_id IN (
			SELECT id FROM chat_sessions WHERE user_id = ? AND id NOT IN (
				SELECT id FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?
			)
		)`, userID, userID, maxSessions)
	if err != nil {
		return fmt.Errorf("prune chat messages: %w", err)
	}
	_, err = s.db.Exec(`
		DELETE FROM chat_sessions WHERE user_id = ? AND id NOT IN (
			SELECT id FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?
		)`, userID, userID, maxSessions)
	if err != nil {
		return fmt.Errorf("prune chat sessions: %w", err)
	}
	return nil
}

func (s *ChatService) RenameSession(id, title string) error {
	_, err := s.db.Exec(`UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?`,
		title, time.Now().UTC().Format(time.RFC3339), id)
	return err
}

func (s *ChatService) SetTitleFromFirstBookIfEmpty(sessionID string, bookIDs []string) error {
	if len(bookIDs) == 0 {
		return nil
	}
	var currentTitle string
	err := s.db.QueryRow(`SELECT title FROM chat_sessions WHERE id = ?`, sessionID).Scan(&currentTitle)
	if err != nil {
		return err
	}
	if currentTitle != "" {
		return nil
	}
	var title string
	err = s.db.QueryRow(`SELECT title FROM books WHERE id = ?`, bookIDs[0]).Scan(&title)
	if err != nil {
		return err
	}
	if title == "" {
		return nil
	}
	_, err = s.db.Exec(`UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?`,
		title, time.Now().UTC().Format(time.RFC3339), sessionID)
	return err
}

func (s *ChatService) TouchSession(id string) error {
	_, err := s.db.Exec(`UPDATE chat_sessions SET updated_at = ? WHERE id = ?`,
		time.Now().UTC().Format(time.RFC3339), id)
	return err
}

func (s *ChatService) AppendMessage(sessionID, role, content, citationsJSON string) error {
	_, err := s.db.Exec(
		`INSERT INTO chat_messages (id, session_id, role, content, citations, created_at) VALUES (?, ?, ?, ?, ?, ?)`,
		uuid.NewString(), sessionID, role, content, citationsJSON, time.Now().UTC().Format(time.RFC3339),
	)
	return err
}

// PromptMessage 是装配后发给 Worker 的单条对话消息。
type PromptMessage struct {
	Role    string
	Content string
}

type promptCitation struct {
	ChapterID string `json:"chapter_id"`
	BookID    string `json:"book_id"`
	Content   string `json:"content"`
}

// BuildPromptMessages 以 DB 为可信来源取最近 windowSize 条消息，
// 并把 assistant 已落库 citations 追加回正文，避免追问丢失上轮依据。
func (s *ChatService) BuildPromptMessages(sessionID string, windowSize int) ([]PromptMessage, error) {
	msgs, err := s.ListMessages(sessionID)
	if err != nil {
		return nil, err
	}
	total := len(msgs)
	if windowSize > 0 && total > windowSize {
		msgs = msgs[total-windowSize:]
	}

	chapterIDs := map[string]struct{}{}
	bookIDs := map[string]struct{}{}
	parsed := make([][]promptCitation, len(msgs))
	for i, m := range msgs {
		if m.Role != models.ChatRoleAssistant || m.Citations == "" || m.Citations == "[]" {
			continue
		}
		var cites []promptCitation
		if err := json.Unmarshal([]byte(m.Citations), &cites); err != nil {
			continue
		}
		parsed[i] = cites
		for _, c := range cites {
			if c.ChapterID != "" {
				chapterIDs[c.ChapterID] = struct{}{}
			}
			if c.BookID != "" {
				bookIDs[c.BookID] = struct{}{}
			}
		}
	}

	chapterTitles, chapterBookIDs, err := s.lookupChapterTitles(chapterIDs)
	if err != nil {
		return nil, err
	}
	for id := range chapterBookIDs {
		bookIDs[id] = struct{}{}
	}
	bookTitles, err := s.lookupBookTitles(bookIDs)
	if err != nil {
		return nil, err
	}

	result := make([]PromptMessage, 0, len(msgs))
	for i, m := range msgs {
		pm := PromptMessage{Role: m.Role, Content: m.Content}
		if lines := buildCitationLines(parsed[i], chapterTitles, chapterBookIDs, bookTitles); len(lines) > 0 {
			pm.Content += "\n\n上一轮回答参考来源：\n" + strings.Join(lines, "\n")
		}
		result = append(result, pm)
	}
	return result, nil
}

func buildCitationLines(
	cites []promptCitation,
	chapterTitles map[string]string,
	chapterBookIDs map[string]string,
	bookTitles map[string]string,
) []string {
	var lines []string
	seen := map[string]struct{}{}
	for _, c := range cites {
		content := strings.TrimSpace(c.Content)
		if content == "" {
			continue
		}
		bookID := c.BookID
		if bookID == "" {
			bookID = chapterBookIDs[c.ChapterID]
		}
		label := chapterTitles[c.ChapterID]
		if label == "" {
			label = "未知章节"
		}
		if bookTitle := bookTitles[bookID]; bookTitle != "" {
			label = "《" + bookTitle + "》" + label
		}
		line := "> [" + label + "]: \"" + content + "\""
		if _, ok := seen[line]; ok {
			continue
		}
		seen[line] = struct{}{}
		lines = append(lines, line)
	}
	return lines
}

func lookupTitleMap(rows *sql.Rows) (map[string]string, error) {
	defer rows.Close()
	out := map[string]string{}
	for rows.Next() {
		var id, title string
		if err := rows.Scan(&id, &title); err != nil {
			return nil, err
		}
		out[id] = title
	}
	return out, rows.Err()
}

func (s *ChatService) lookupChapterTitles(ids map[string]struct{}) (map[string]string, map[string]string, error) {
	titles := map[string]string{}
	bookIDs := map[string]string{}
	if len(ids) == 0 {
		return titles, bookIDs, nil
	}
	idList := make([]any, 0, len(ids))
	placeholders := make([]string, 0, len(ids))
	for id := range ids {
		idList = append(idList, id)
		placeholders = append(placeholders, "?")
	}
	query := `SELECT id, COALESCE(book_id, ''), title FROM chapters WHERE id IN (` + strings.Join(placeholders, ",") + `)`
	rows, err := s.db.Query(query, idList...)
	if err != nil {
		return nil, nil, fmt.Errorf("lookup chapter titles: %w", err)
	}
	defer rows.Close()
	for rows.Next() {
		var id, bookID, title string
		if err := rows.Scan(&id, &bookID, &title); err != nil {
			return nil, nil, fmt.Errorf("scan chapter title: %w", err)
		}
		titles[id] = title
		bookIDs[id] = bookID
	}
	return titles, bookIDs, rows.Err()
}

func (s *ChatService) lookupBookTitles(ids map[string]struct{}) (map[string]string, error) {
	if len(ids) == 0 {
		return map[string]string{}, nil
	}
	idList := make([]any, 0, len(ids))
	placeholders := make([]string, 0, len(ids))
	for id := range ids {
		idList = append(idList, id)
		placeholders = append(placeholders, "?")
	}
	query := `SELECT id, title FROM books WHERE id IN (` + strings.Join(placeholders, ",") + `)`
	rows, err := s.db.Query(query, idList...)
	if err != nil {
		return nil, fmt.Errorf("lookup book titles: %w", err)
	}
	return lookupTitleMap(rows)
}

func (s *ChatService) ListMessages(sessionID string) ([]models.ChatMessage, error) {
	rows, err := s.db.Query(
		`SELECT id, session_id, role, content, citations, created_at
		 FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC`, sessionID)
	if err != nil {
		return nil, fmt.Errorf("list chat messages: %w", err)
	}
	defer rows.Close()

	var messages []models.ChatMessage
	for rows.Next() {
		var m models.ChatMessage
		if err := rows.Scan(&m.ID, &m.SessionID, &m.Role, &m.Content, &m.Citations, &m.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan chat message: %w", err)
		}
		messages = append(messages, m)
	}
	return messages, rows.Err()
}
