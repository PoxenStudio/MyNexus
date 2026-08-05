package middleware

import (
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

// bucket is a simple token bucket: refills at rate tokens/sec up to capacity.
type bucket struct {
	tokens   float64
	lastFill time.Time
}

// RateLimit throttles requests per client IP using an in-memory token bucket
// per docs/系统设计文档.md §8.3 (no external dependency like Redis — a single
// NAS-hosted process doesn't need one). ratePerSecond replenishes the bucket;
// burst caps how many requests can fire back-to-back.
func RateLimit(ratePerSecond float64, burst int) gin.HandlerFunc {
	var mu sync.Mutex
	buckets := map[string]*bucket{}

	return func(c *gin.Context) {
		key := c.ClientIP()

		mu.Lock()
		b, ok := buckets[key]
		now := time.Now()
		if !ok {
			b = &bucket{tokens: float64(burst), lastFill: now}
			buckets[key] = b
		} else {
			elapsed := now.Sub(b.lastFill).Seconds()
			b.tokens += elapsed * ratePerSecond
			if b.tokens > float64(burst) {
				b.tokens = float64(burst)
			}
			b.lastFill = now
		}

		allowed := b.tokens >= 1
		if allowed {
			b.tokens--
		}
		mu.Unlock()

		if !allowed {
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{"error": "rate limit exceeded, please retry later"})
			return
		}
		c.Next()
	}
}
