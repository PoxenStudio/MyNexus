package middleware

import (
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/service"
)

// APITokenAuth validates an `Authorization: Bearer mnx_...` header against
// api_tokens when present (docs/系统设计文档.md §2.2's API Token path). If no
// Authorization header is given at all, the request is allowed through
// unauthenticated — Core API has no user accounts/login yet (see
// .claude/memory/mynexus_m2_decisions.md), so hard-requiring a token on every
// route would break the admin UI, which has no login flow to obtain one.
// A *present but invalid/revoked* token is always rejected.
func APITokenAuth(tokens *service.TokenService, tokenPrefix string) gin.HandlerFunc {
	return func(c *gin.Context) {
		header := c.GetHeader("Authorization")
		if header == "" {
			c.Next()
			return
		}

		raw, ok := strings.CutPrefix(header, "Bearer ")
		if !ok || !strings.HasPrefix(raw, tokenPrefix) {
			// Not an API Token (e.g. a future JWT) — let it through unchecked
			// for now, since JWT auth isn't implemented (see docs §15).
			c.Next()
			return
		}

		userID, valid := tokens.Authenticate(raw)
		if !valid {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid or revoked API token"})
			return
		}
		c.Set("user_id", userID)
		c.Next()
	}
}
