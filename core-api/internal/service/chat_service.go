package service

import (
	"database/sql"
	"fmt"
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

func (s *ChatService) DeleteSession(id string) error {
	_, err := s.db.Exec(`DELETE FROM chat_sessions WHERE id = ?`, id)
	return err
}

func (s *ChatService) RenameSession(id, title string) error {
	_, err := s.db.Exec(`UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?`,
		title, time.Now().UTC().Format(time.RFC3339), id)
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
