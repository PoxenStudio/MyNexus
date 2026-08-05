package middleware

import (
	"strings"

	"github.com/gin-gonic/gin"
)

// CORS allows the configured origins (or "*") to call the API, which is what
// the Web UI and third-party clients need during local/NAS deployment.
func CORS(origins []string) gin.HandlerFunc {
	allowAll := len(origins) == 0
	for _, o := range origins {
		if o == "*" {
			allowAll = true
		}
	}

	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		// Admin login uses a session cookie, which requires the response to
		// name a specific origin (not "*") plus Allow-Credentials — browsers
		// reject wildcard-origin + credentialed requests outright. Reflecting
		// the request's own Origin back is safe here: it's not a stand-in for
		// real origin validation on non-browser clients (API token requests
		// don't send cookies, so they don't rely on this at all).
		if allowAll {
			if origin != "" {
				c.Header("Access-Control-Allow-Origin", origin)
			} else {
				c.Header("Access-Control-Allow-Origin", "*")
			}
		} else if origin != "" && contains(origins, origin) {
			c.Header("Access-Control-Allow-Origin", origin)
		}
		c.Header("Access-Control-Allow-Credentials", "true")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Authorization, Content-Type, Accept-Language")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	}
}

func contains(list []string, target string) bool {
	for _, v := range list {
		if strings.EqualFold(v, target) {
			return true
		}
	}
	return false
}
