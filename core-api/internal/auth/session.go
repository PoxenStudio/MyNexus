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
	role      string
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

// Create stores username/role alongside userID so RequireAuth/audit logging
// can label actions and gate admin-only routes without an extra DB lookup
// per request. Note: role is snapshotted at login time — if an admin changes
// a logged-in user's role or disables their account, that only takes effect
// once this session expires (SessionTTL, 24h) or the user logs in again; see
// .claude/memory/mynexus_user_management.md for why immediate revocation
// wasn't implemented.
func (m *SessionManager) Create(userID, username, role string) (string, error) {
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	id := hex.EncodeToString(buf)

	m.mu.Lock()
	m.sessions[id] = session{userID: userID, username: username, role: role, expiresAt: time.Now().Add(SessionTTL)}
	m.mu.Unlock()
	return id, nil
}

func (m *SessionManager) Validate(id string) (userID, username, role string, ok bool) {
	if id == "" {
		return "", "", "", false
	}
	m.mu.Lock()
	defer m.mu.Unlock()

	s, found := m.sessions[id]
	if !found {
		return "", "", "", false
	}
	if time.Now().After(s.expiresAt) {
		delete(m.sessions, id)
		return "", "", "", false
	}
	return s.userID, s.username, s.role, true
}

func (m *SessionManager) Delete(id string) {
	m.mu.Lock()
	delete(m.sessions, id)
	m.mu.Unlock()
}
