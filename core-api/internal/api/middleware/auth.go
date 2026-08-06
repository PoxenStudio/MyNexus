package middleware

import (
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/auth"
	"mynexus/core-api/internal/service"
)

// RequireAuth accepts either a valid admin session cookie (browser use of the
// admin web-ui — see AuthHandler.Login) or a valid `Authorization: Bearer
// mnx_...` API token (service/automation access — see TokenService and the
// Tokens admin page). Exactly one of the two is required; requests with
// neither are rejected. This replaced the earlier "enforced only if a header
// is present" behavior now that a real login flow exists (see
// .claude/memory/mynexus_known_gaps_and_conflicts.md's now-resolved
// "auth is enforced-when-present, not required" gap).
func RequireAuth(sessions *auth.SessionManager, tokens *service.TokenService, tokenPrefix string) gin.HandlerFunc {
	return func(c *gin.Context) {
		if sid, err := c.Cookie(auth.SessionCookieName); err == nil {
			if userID, username, role, ok := sessions.Validate(sid); ok {
				c.Set("admin_user_id", userID)
				c.Set("user_id", userID)
				c.Set("role", role)
				// "actor" labels audit log entries with a human-readable name
				// (see AuditService) — the user's own username for browser
				// sessions, "token:<alias>" for API Token access below.
				c.Set("actor", username)
				c.Next()
				return
			}
		}

		if header := c.GetHeader("Authorization"); header != "" {
			if raw, ok := strings.CutPrefix(header, "Bearer "); ok && strings.HasPrefix(raw, tokenPrefix) {
				if userID, alias, valid := tokens.Authenticate(raw); valid {
					c.Set("user_id", userID)
					// API tokens are an admin/automation concern (see the
					// Tokens admin page) — treat token-authenticated
					// requests as admin-equivalent for RequireAdmin.
					c.Set("role", "admin")
					actor := "token"
					if alias != "" {
						actor = "token:" + alias
					}
					c.Set("actor", actor)
					c.Next()
					return
				}
				c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid or revoked API token"})
				return
			}
		}

		c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "authentication required"})
	}
}

// RequireAdmin gates routes to the "admin" role only — plain "user" accounts
// (chat + own profile) get a 403. Must run after RequireAuth so "role" is
// already set in context.
func RequireAdmin() gin.HandlerFunc {
	return func(c *gin.Context) {
		role, _ := c.Get("role")
		if role != "admin" {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "admin role required"})
			return
		}
		c.Next()
	}
}

// RequireChatEnabled gates the conversation ("会话") feature behind
// config.Chat.Enabled — some deployments may not want an AI chat surface
// exposed at all (e.g. no LLM budget configured).
func RequireChatEnabled(enabled bool) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !enabled {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "chat feature is disabled"})
			return
		}
		c.Next()
	}
}
