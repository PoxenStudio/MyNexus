package api

import (
	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/handler"
	"mynexus/core-api/internal/api/middleware"
	"mynexus/core-api/internal/config"
	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/service"
	"mynexus/core-api/internal/storage/sqlite"
)

// NewRouter wires up all routes. Auth middleware joins this once M4 lands
// (see docs/开发技术文档.md §15 for the current API Token / JWT decision).
func NewRouter(cfg config.Config, store *sqlite.Store) *gin.Engine {
	r := gin.New()
	r.Use(gin.Recovery(), gin.Logger())
	r.Use(middleware.CORS(cfg.Server.CORSOrigins))

	db := store.DB()
	bookSvc := service.NewBookService(db, cfg.Storage.UploadDir)
	taskSvc := service.NewTaskService(db)
	chatSvc := service.NewChatService(db)
	workerClient := coordinator.NewWorkerClient(cfg.Worker.URL)

	sys := handler.NewSystemHandler(cfg, store)
	books := handler.NewBookHandler(cfg, bookSvc, taskSvc, workerClient)
	tasks := handler.NewTaskHandler(taskSvc)
	search := handler.NewSearchHandler(bookSvc, workerClient)
	chat := handler.NewChatHandler(chatSvc, workerClient)
	internalH := handler.NewInternalHandler(bookSvc, taskSvc)

	r.GET("/healthz", sys.Health)

	v1 := r.Group("/api/v1")
	{
		v1.GET("/system/health", sys.Health)
		v1.GET("/system/stats", sys.Stats)

		v1.POST("/books/import", books.Import)
		v1.GET("/books", books.List)
		v1.GET("/books/:id", books.Get)
		v1.PUT("/books/:id", books.Update)
		v1.DELETE("/books/:id", books.Delete)
		v1.GET("/books/:id/chunks", books.Chunks)

		v1.GET("/tasks", tasks.List)
		v1.GET("/tasks/:id", tasks.Get)

		v1.POST("/search/hybrid", search.Hybrid)

		v1.POST("/chat/completions", chat.Completions)
		v1.GET("/chat/sessions", chat.ListSessions)
		v1.GET("/chat/sessions/:id", chat.GetSession)
		v1.DELETE("/chat/sessions/:id", chat.DeleteSession)
	}

	internalGroup := r.Group("/internal")
	{
		internalGroup.POST("/tasks/:id/progress", internalH.Progress)
		internalGroup.POST("/tasks/:id/complete", internalH.Complete)
		internalGroup.POST("/tasks/:id/fail", internalH.Fail)
	}

	return r
}
