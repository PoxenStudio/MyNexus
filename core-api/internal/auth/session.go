package auth

import (
	"crypto/rand"
	"encoding/hex"
	"sync"
	"time"
)

const SessionCookieName = "mnx_session"

// SessionTTL is fixed (no sliding renewal) — simple and consistent with the
// project's other in-memory, single-process state (see middleware.RateLimit).
const SessionTTL = 24 * time.Hour

type session struct {
	userID    string
	username  string
	expiresAt time.Time
}

// SessionManager is an in-memory admin login session store. No Redis/external
// store, matching the single-process-per-NAS deployment model used elsewhere
// (rate limiting, etc.) — sessions are lost on restart, which just means
// admins log in again, an acceptable tradeoff for a private single-admin tool.
type SessionManager struct {
	mu       sync.Mutex
	sessions map[string]session
}

func NewSessionManager() *SessionManager {
	return &SessionManager{sessions: map[string]session{}}
}

// Create stores username alongside userID so RequireAuth/audit logging can
// label actions with a human-readable actor without an extra DB lookup per
// request.
func (m *SessionManager) Create(userID, username string) (string, error) {
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	id := hex.EncodeToString(buf)

	m.mu.Lock()
	m.sessions[id] = session{userID: userID, username: username, expiresAt: time.Now().Add(SessionTTL)}
	m.mu.Unlock()
	return id, nil
}

func (m *SessionManager) Validate(id string) (userID, username string, ok bool) {
	if id == "" {
		return "", "", false
	}
	m.mu.Lock()
	defer m.mu.Unlock()

	s, found := m.sessions[id]
	if !found {
		return "", "", false
	}
	if time.Now().After(s.expiresAt) {
		delete(m.sessions, id)
		return "", "", false
	}
	return s.userID, s.username, true
}

func (m *SessionManager) Delete(id string) {
	m.mu.Lock()
	delete(m.sessions, id)
	m.mu.Unlock()
}
