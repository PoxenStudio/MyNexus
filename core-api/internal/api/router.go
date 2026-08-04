package api

import (
	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/handler"
	"mynexus/core-api/internal/api/middleware"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/storage/sqlite"
)

// NewRouter wires the M1 skeleton routes. Business-domain handlers (books,
// tasks, search, chat, tokens) join this group starting M2.
func NewRouter(cfg config.Config, store *sqlite.Store) *gin.Engine {
	r := gin.New()
	r.Use(gin.Recovery(), gin.Logger())
	r.Use(middleware.CORS(cfg.Server.CORSOrigins))

	sys := handler.NewSystemHandler(cfg, store)

	r.GET("/healthz", sys.Health)

	v1 := r.Group("/api/v1")
	{
		v1.GET("/system/health", sys.Health)
		v1.GET("/system/stats", sys.Stats)
	}

	return r
}
