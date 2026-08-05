package config

import (
	"os"
	"strconv"

	"gopkg.in/yaml.v3"
)

type ServerConfig struct {
	Port        string   `yaml:"port"`
	CORSOrigins []string `yaml:"cors_origins"`
	// GRPCPort is where Core API's gRPC server listens for Worker-initiated
	// calls (ReportProgress/ReportComplete/ReportFail/KeywordSearch) — see
	// .claude/memory/mynexus_grpc_migration.md. Separate from Port (the
	// browser-facing HTTP/SSE API), which is unaffected by this.
	// Worker finds this address via its own config.yaml's server.internal_url
	// (Worker-side key, not read here — see worker/src/config.py); Core API
	// only needs to know which local port to bind.
	GRPCPort string `yaml:"grpc_port"`
}

type AuthConfig struct {
	JWTSecret   string `yaml:"jwt_secret"`
	TokenPrefix string `yaml:"token_prefix"`
}

type SQLiteConfig struct {
	Path string `yaml:"path"`
}

type PostgresConfig struct {
	DSN string `yaml:"dsn"`
}

type StorageConfig struct {
	// Database selects the backend: "sqlite" (default, single-file, NAS/single-instance
	// deployments) or "postgres" (better concurrent-write performance, for larger/multi-
	// instance deployments). See docs/系统设计文档.md §3.x and docs/Todos.md.
	Database    string         `yaml:"database"`
	SQLite      SQLiteConfig   `yaml:"sqlite"`
	Postgres    PostgresConfig `yaml:"postgres"`
	VectorStore string         `yaml:"vector_store"`
	UploadDir   string         `yaml:"upload_dir"`
}

type WorkerConfig struct {
	// URL is Worker's gRPC dial target — a bare "host:port" authority (e.g.
	// "worker:8001" in Docker, "localhost:8001" locally), NOT an "http://" URL
	// (repurposed from the pre-gRPC-migration HTTP client base URL — see
	// .claude/memory/mynexus_grpc_migration.md).
	URL                string `yaml:"url"`
	MaxConcurrentTasks int    `yaml:"max_concurrent_tasks"`
	TaskTimeoutSeconds int    `yaml:"task_timeout_seconds"`
}

type I18nConfig struct {
	DefaultLocale string   `yaml:"default_locale"`
	Supported     []string `yaml:"supported"`
}

// ChatConfig gates the end-user conversation ("会话") page/feature. When
// disabled, the /chat/* API rejects requests and the web-ui hides/blocks the
// conversation page — some deployments may not want an AI chat surface
// exposed at all (e.g. no LLM budget configured).
type ChatConfig struct {
	Enabled bool `yaml:"enabled"`
}

type Config struct {
	Server  ServerConfig  `yaml:"server"`
	Auth    AuthConfig    `yaml:"auth"`
	Storage StorageConfig `yaml:"storage"`
	Worker  WorkerConfig  `yaml:"worker"`
	I18n    I18nConfig    `yaml:"i18n"`
	Chat    ChatConfig    `yaml:"chat"`

	// Port kept for backward-compatible direct access; mirrors Server.Port.
	Port string
}

func defaults() Config {
	return Config{
		Server: ServerConfig{Port: "8080", CORSOrigins: []string{"*"}, GRPCPort: "9090"},
		Auth:   AuthConfig{TokenPrefix: "mnx_"},
		Storage: StorageConfig{
			Database:  "sqlite",
			SQLite:    SQLiteConfig{Path: "./data/mynexus.db"},
			UploadDir: "./data/uploads",
		},
		Worker: WorkerConfig{URL: "localhost:8001", MaxConcurrentTasks: 1, TaskTimeoutSeconds: 600},
		I18n:   I18nConfig{DefaultLocale: "zh-CN", Supported: []string{"zh-CN", "zh-TW", "en-US"}},
		Chat:   ChatConfig{Enabled: true},
	}
}

// Load reads config.yaml (path from MYNEXUS_CONFIG_PATH, default ./config/config.yaml),
// falling back to built-in defaults when the file is absent, then applies environment
// variable overrides so Docker deployments can inject secrets without editing the file.
func Load() Config {
	cfg := defaults()

	path := os.Getenv("MYNEXUS_CONFIG_PATH")
	if path == "" {
		path = "./config/config.yaml"
	}
	if data, err := os.ReadFile(path); err == nil {
		_ = yaml.Unmarshal(data, &cfg)
	}

	if v := os.Getenv("MYNEXUS_SERVER_PORT"); v != "" {
		cfg.Server.Port = v
	} else if v := os.Getenv("PORT"); v != "" {
		cfg.Server.Port = v
	}
	if v := os.Getenv("MYNEXUS_AUTH_JWT_SECRET"); v != "" {
		cfg.Auth.JWTSecret = v
	}
	if v := os.Getenv("MYNEXUS_WORKER_URL"); v != "" {
		cfg.Worker.URL = v
	}
	if v := os.Getenv("MYNEXUS_STORAGE_SQLITE_PATH"); v != "" {
		cfg.Storage.SQLite.Path = v
	}
	if v := os.Getenv("MYNEXUS_STORAGE_DATABASE"); v != "" {
		cfg.Storage.Database = v
	}
	if v := os.Getenv("MYNEXUS_STORAGE_POSTGRES_DSN"); v != "" {
		cfg.Storage.Postgres.DSN = v
	}
	if v := os.Getenv("MYNEXUS_STORAGE_UPLOAD_DIR"); v != "" {
		cfg.Storage.UploadDir = v
	}
	if v := os.Getenv("MYNEXUS_SERVER_GRPC_PORT"); v != "" {
		cfg.Server.GRPCPort = v
	}
	if v := os.Getenv("MYNEXUS_CHAT_ENABLED"); v != "" {
		if b, err := strconv.ParseBool(v); err == nil {
			cfg.Chat.Enabled = b
		}
	}

	cfg.Port = cfg.Server.Port
	return cfg
}
