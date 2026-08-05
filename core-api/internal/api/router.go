package api

import (
	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/handler"
	"mynexus/core-api/internal/api/middleware"
	"mynexus/core-api/internal/auth"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/service"
	"mynexus/core-api/internal/storage"
)

// NewRouter wires up all routes. Admin web-ui access requires a login session
// (see AuthHandler/middleware.RequireAuth); service/automation access uses an
// API Token instead (see the Tokens admin page) — either is accepted on
// protected routes. store is backend-agnostic (sqlite or postgres, see
// storage.Database) — the service layer below only ever sees the shared *sql.DB.
func NewRouter(cfg config.Config, store storage.Database) *gin.Engine {
	r := gin.New()
	r.Use(gin.Recovery(), gin.Logger())
	r.Use(middleware.CORS(cfg.Server.CORSOrigins))
	r.Use(middleware.RateLimit(20, 40))

	db := store.DB()
	bookSvc := service.NewBookService(db, cfg.Storage.UploadDir)
	taskSvc := service.NewTaskService(db)
	chatSvc := service.NewChatService(db)
	tokenSvc := service.NewTokenService(db, cfg.Auth.TokenPrefix)
	adminSvc := service.NewAdminUserService(db)
	auditSvc := service.NewAuditService(db)
	sessions := auth.NewSessionManager()
	workerClient := coordinator.NewWorkerClient(cfg.Worker.URL)

	sys := handler.NewSystemHandler(cfg, store)
	books := handler.NewBookHandler(cfg, bookSvc, taskSvc, workerClient, auditSvc)
	tasks := handler.NewTaskHandler(cfg, taskSvc, bookSvc, workerClient, auditSvc)
	search := handler.NewSearchHandler(bookSvc, workerClient)
	chat := handler.NewChatHandler(chatSvc, workerClient)
	tokens := handler.NewTokenHandler(tokenSvc, auditSvc)
	authH := handler.NewAuthHandler(adminSvc, sessions, auditSvc)
	auditH := handler.NewAuditHandler(auditSvc)
	internalH := handler.NewInternalHandler(bookSvc, taskSvc)

	r.GET("/healthz", sys.Health)

	v1 := r.Group("/api/v1")
	{
		// Login/logout must be reachable without an existing session/token.
		v1.POST("/auth/login", authH.Login)
		v1.POST("/auth/logout", authH.Logout)
	}

	protected := v1.Group("")
	protected.Use(middleware.RequireAuth(sessions, tokenSvc, cfg.Auth.TokenPrefix))
	{
		protected.GET("/auth/me", authH.Me)
		protected.POST("/auth/change-password", authH.ChangePassword)

		protected.GET("/system/health", sys.Health)
		protected.GET("/system/stats", sys.Stats)
		protected.GET("/system/config", sys.Config)

		protected.POST("/books/import", books.Import)
		protected.GET("/books", books.List)
		protected.GET("/books/:id", books.Get)
		protected.PUT("/books/:id", books.Update)
		protected.DELETE("/books/:id", books.Delete)
		protected.GET("/books/:id/chunks", books.Chunks)

		protected.GET("/tasks", tasks.List)
		protected.GET("/tasks/:id", tasks.Get)
		protected.POST("/tasks/:id/retry", tasks.Retry)

		protected.POST("/search/hybrid", search.Hybrid)

		protected.POST("/tokens", tokens.Create)
		protected.GET("/tokens", tokens.List)
		protected.DELETE("/tokens/:id", tokens.Revoke)

		protected.GET("/audit-log", auditH.List)

		chatGroup := protected.Group("/chat")
		chatGroup.Use(middleware.RequireChatEnabled(cfg.Chat.Enabled))
		{
			chatGroup.POST("/completions", chat.Completions)
			chatGroup.GET("/sessions", chat.ListSessions)
			chatGroup.GET("/sessions/:id", chat.GetSession)
			chatGroup.DELETE("/sessions/:id", chat.DeleteSession)
		}
	}

	internalGroup := r.Group("/internal")
	{
		internalGroup.POST("/tasks/:id/progress", internalH.Progress)
		internalGroup.POST("/tasks/:id/complete", internalH.Complete)
		internalGroup.POST("/tasks/:id/fail", internalH.Fail)
	}

	return r
}
