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
// workerClient is constructed once in main.go (not here) so it can also be
// shared with the Worker health-check loop (main.go's watchWorkerHealth) —
// one persistent gRPC connection to Worker, not two.
func NewRouter(cfg config.Config, store storage.Database, workerClient *coordinator.WorkerClient) *gin.Engine {
	r := gin.New()
	r.Use(gin.Recovery(), gin.Logger())
	r.Use(middleware.CORS(cfg.Server.CORSOrigins))
	r.Use(middleware.RateLimit(20, 40))

	db := store.DB()
	bookSvc := service.NewBookService(db, cfg.Storage.UploadDir)
	taskSvc := service.NewTaskService(db)
	chatSvc := service.NewChatService(db)
	tokenSvc := service.NewTokenService(db, cfg.Auth.TokenPrefix)
	userSvc := service.NewUserService(db)
	auditSvc := service.NewAuditService(db)
	sessions := auth.NewSessionManager()

	sys := handler.NewSystemHandler(cfg, store, workerClient, auditSvc)
	books := handler.NewBookHandler(cfg, bookSvc, taskSvc, workerClient, auditSvc)
	tasks := handler.NewTaskHandler(cfg, taskSvc, bookSvc, workerClient, auditSvc)
	search := handler.NewSearchHandler(bookSvc, workerClient)
	chat := handler.NewChatHandler(chatSvc, workerClient)
	tokens := handler.NewTokenHandler(tokenSvc, auditSvc)
	authH := handler.NewAuthHandler(userSvc, sessions, auditSvc, cfg.Storage.UploadDir)
	auditH := handler.NewAuditHandler(auditSvc)
	usersH := handler.NewUserHandler(userSvc, auditSvc)

	r.GET("/healthz", sys.Health)

	v1 := r.Group("/api/v1")
	{
		// Login/logout must be reachable without an existing session/token.
		v1.POST("/auth/login", authH.Login)
		v1.POST("/auth/logout", authH.Logout)
	}

	// protected: reachable by both roles (admin + plain user) once logged in.
	// adminOnly: dashboard/back-office routes — everything a "user" role
	// account must NOT see (books, tasks, tokens, audit log, system config,
	// user management). See middleware.RequireAdmin and the frontend's
	// meta.requiresAdmin route guard for the matching UI-side gate.
	protected := v1.Group("")
	protected.Use(middleware.RequireAuth(sessions, tokenSvc, cfg.Auth.TokenPrefix))
	{
		protected.GET("/auth/me", authH.Me)
		protected.POST("/auth/change-password", authH.ChangePassword)
		protected.POST("/auth/avatar", authH.UploadAvatar)
		protected.GET("/auth/avatar/:id", authH.ServeAvatar)

		chatGroup := protected.Group("/chat")
		chatGroup.Use(middleware.RequireChatEnabled(cfg.Chat.Enabled))
		{
			chatGroup.POST("/completions", chat.Completions)
			chatGroup.GET("/sessions", chat.ListSessions)
			chatGroup.GET("/sessions/:id", chat.GetSession)
			chatGroup.PUT("/sessions/:id", chat.RenameSession)
			chatGroup.DELETE("/sessions/:id", chat.DeleteSession)
		}

		adminOnly := protected.Group("")
		adminOnly.Use(middleware.RequireAdmin())
		{
			adminOnly.GET("/system/health", sys.Health)
			adminOnly.GET("/system/stats", sys.Stats)
			adminOnly.GET("/system/config", sys.Config)
			adminOnly.GET("/system/settings", sys.Settings)
			adminOnly.PUT("/system/settings", sys.SaveSettings)

			adminOnly.POST("/books/import", books.Import)
			adminOnly.POST("/books/bulk-delete", books.BulkDelete)
			adminOnly.POST("/books/bulk-rebuild", books.BulkRebuild)
			adminOnly.GET("/books", books.List)
			adminOnly.GET("/books/:id", books.Get)
			adminOnly.PUT("/books/:id", books.Update)
			adminOnly.DELETE("/books/:id", books.Delete)
			adminOnly.GET("/books/:id/chunks", books.Chunks)
			adminOnly.POST("/books/:id/rebuild", books.Rebuild)
			adminOnly.POST("/books/:id/summarize", books.Summarize)

			adminOnly.GET("/tasks", tasks.List)
			adminOnly.GET("/tasks/:id", tasks.Get)
			adminOnly.POST("/tasks/:id/retry", tasks.Retry)

			adminOnly.POST("/search/hybrid", search.Hybrid)

			adminOnly.POST("/tokens", tokens.Create)
			adminOnly.GET("/tokens", tokens.List)
			adminOnly.DELETE("/tokens/:id", tokens.Revoke)

			adminOnly.GET("/audit-log", auditH.List)

			adminOnly.GET("/users", usersH.List)
			adminOnly.POST("/users", usersH.Create)
			adminOnly.PUT("/users/:id/role", usersH.SetRole)
			adminOnly.PUT("/users/:id/status", usersH.SetStatus)
			adminOnly.PUT("/users/:id/password", usersH.ResetPassword)
		}
	}

	// Worker-facing calls (task progress/complete/fail, keyword search) are no
	// longer HTTP — see internal/grpcserver, started separately in main.go.

	return r
}
