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
	// InternalURL is Worker-side only (worker/src/config.py's core_api_base_url) —
	// Core API never reads it, but it must round-trip through LoadFromFile/
	// SaveToFile (system_settings.go) like every other field here, or saving
	// unrelated settings would silently delete Worker's dial-back address.
	InternalURL string `yaml:"internal_url"`
}

type AuthConfig struct {
	JWTSecret   string `yaml:"jwt_secret"`
	TokenPrefix string `yaml:"token_prefix"`
}

type SQLiteConfig struct {
	Path string `yaml:"path" json:"path"`
}

type PostgresConfig struct {
	DSN string `yaml:"dsn" json:"dsn"`
}

// StorageConfig, WorkerConfig, EmbeddingConfig, LLMConfig, ProviderConfig,
// SplitterConfig, I18nConfig and ChatConfig all carry json tags in addition
// to yaml, since the system settings page (system_settings.go) marshals them
// straight to/from the PUT /system/settings request body — one struct shape
// for both the config file and the API.
type StorageConfig struct {
	// Database selects the backend: "sqlite" (default, single-file, NAS/single-instance
	// deployments) or "postgres" (better concurrent-write performance, for larger/multi-
	// instance deployments). See docs/系统设计文档.md §3.x and docs/Todos.md.
	Database    string         `yaml:"database" json:"database"`
	SQLite      SQLiteConfig   `yaml:"sqlite" json:"sqlite"`
	Postgres    PostgresConfig `yaml:"postgres" json:"postgres"`
	VectorStore string         `yaml:"vector_store" json:"vector_store"`
	// VectorStorePath is Worker-side only (worker/src/config.py's
	// vector_store_path) — same round-trip-fidelity reasoning as
	// ServerConfig.InternalURL above.
	VectorStorePath string `yaml:"vector_store_path" json:"vector_store_path"`
	UploadDir       string `yaml:"upload_dir" json:"upload_dir"`
}

type WorkerConfig struct {
	// URL is Worker's gRPC dial target — a bare "host:port" authority (e.g.
	// "worker:8001" in Docker, "localhost:8001" locally), NOT an "http://" URL
	// (repurposed from the pre-gRPC-migration HTTP client base URL — see
	// .claude/memory/mynexus_grpc_migration.md).
	URL                string `yaml:"url" json:"url"`
	MaxConcurrentTasks int    `yaml:"max_concurrent_tasks" json:"max_concurrent_tasks"`
	TaskTimeoutSeconds int    `yaml:"task_timeout_seconds" json:"task_timeout_seconds"`
}

// ProviderConfig mirrors worker/src/config.py's ProviderConfig (same field
// set for both an OpenAI-compatible and an Ollama endpoint — APIKey stays
// unused/empty for Ollama). Core API never reads these values itself (only
// Worker does, when it embeds/generates), but the system settings page
// (system_settings.go) needs a typed shape to read/write this part of
// config.yaml, since it owns config.yaml as the single source of truth.
type ProviderConfig struct {
	APIKey  string `yaml:"api_key" json:"api_key"`
	BaseURL string `yaml:"base_url" json:"base_url"`
	Model   string `yaml:"model" json:"model"`
}

type EmbeddingConfig struct {
	Provider string         `yaml:"provider" json:"provider"`
	OpenAI   ProviderConfig `yaml:"openai" json:"openai"`
	Ollama   ProviderConfig `yaml:"ollama" json:"ollama"`
}

type LLMConfig struct {
	Provider string         `yaml:"provider" json:"provider"`
	OpenAI   ProviderConfig `yaml:"openai" json:"openai"`
	Ollama   ProviderConfig `yaml:"ollama" json:"ollama"`
}

type SplitterConfig struct {
	ChunkSize    int    `yaml:"chunk_size" json:"chunk_size"`
	ChunkOverlap int    `yaml:"chunk_overlap" json:"chunk_overlap"`
	Strategy     string `yaml:"strategy" json:"strategy"`
}

type I18nConfig struct {
	DefaultLocale string   `yaml:"default_locale" json:"default_locale"`
	Supported     []string `yaml:"supported" json:"supported"`
}

// ChatConfig gates the end-user conversation ("会话") page/feature. When
// disabled, the /chat/* API rejects requests and the web-ui hides/blocks the
// conversation page — some deployments may not want an AI chat surface
// exposed at all (e.g. no LLM budget configured).
type ChatConfig struct {
	Enabled bool `yaml:"enabled" json:"enabled"`
}

// DebugConfig is Worker-side only (Core API never reads it, same round-trip-
// fidelity reasoning as ServerConfig.InternalURL above) — it just needs to
// survive SaveToFile since the system settings page writes the whole Config.
// LLMLogging, when true, makes every LLM call (worker/src/nodes/llm/*.py)
// dump its request messages and full response text as a matched pair of
// files under the OS temp dir (see worker/src/util/debug_log.py and
// docs/部署说明.md "调试日志") — replay one with worker/tests/replay_llm_debug.py.
type DebugConfig struct {
	LLMLogging bool `yaml:"llm_logging" json:"llm_logging"`
}

// KeywordConfig caps how many whole-book content keywords (books.keywords —
// see worker/src/pipelines/summary.py) a book detail response returns.
// Applied at read time (dto.NewBookResponse), not at extraction/storage
// time, so raising the limit surfaces more of a book's already-extracted
// keywords immediately without re-summarizing it.
type KeywordConfig struct {
	MaxKeywords int `yaml:"max_keywords" json:"max_keywords"`
}

type Config struct {
	Server    ServerConfig    `yaml:"server"`
	Auth      AuthConfig      `yaml:"auth"`
	Storage   StorageConfig   `yaml:"storage"`
	Worker    WorkerConfig    `yaml:"worker"`
	Embedding EmbeddingConfig `yaml:"embedding"`
	LLM       LLMConfig       `yaml:"llm"`
	Splitter  SplitterConfig  `yaml:"splitter"`
	I18n      I18nConfig      `yaml:"i18n"`
	Chat      ChatConfig      `yaml:"chat"`
	Keyword   KeywordConfig   `yaml:"keyword"`
	Debug     DebugConfig     `yaml:"debug"`

	// Port kept for backward-compatible direct access; mirrors Server.Port.
	// yaml:"-" so SaveToFile doesn't emit a spurious top-level "port" key.
	Port string `yaml:"-"`
}

func defaults() Config {
	return Config{
		Server: ServerConfig{Port: "8080", CORSOrigins: []string{"*"}, GRPCPort: "9090", InternalURL: "localhost:9090"},
		Auth:   AuthConfig{TokenPrefix: "mnx_"},
		Storage: StorageConfig{
			Database:        "sqlite",
			SQLite:          SQLiteConfig{Path: "./data/mynexus.db"},
			VectorStore:     "chroma",
			VectorStorePath: "./data/vectorstore",
			UploadDir:       "./data/uploads",
		},
		Worker: WorkerConfig{URL: "localhost:8001", MaxConcurrentTasks: 1, TaskTimeoutSeconds: 600},
		// Embedding/LLM/Splitter defaults mirror worker/src/config.py's
		// dataclass defaults — keep the two in sync if either changes.
		Embedding: EmbeddingConfig{
			Provider: "openai",
			OpenAI:   ProviderConfig{BaseURL: "https://api.openai.com/v1", Model: "text-embedding-3-small"},
			Ollama:   ProviderConfig{BaseURL: "http://localhost:11434", Model: "nomic-embed-text"},
		},
		LLM: LLMConfig{
			Provider: "openai",
			OpenAI:   ProviderConfig{BaseURL: "https://api.openai.com/v1", Model: "gpt-4o-mini"},
			Ollama:   ProviderConfig{BaseURL: "http://localhost:11434", Model: "llama3"},
		},
		Splitter: SplitterConfig{ChunkSize: 500, ChunkOverlap: 50, Strategy: "token"},
		I18n:     I18nConfig{DefaultLocale: "zh-CN", Supported: []string{"zh-CN", "zh-TW", "en-US"}},
		Chat:     ChatConfig{Enabled: true},
		Keyword:  KeywordConfig{MaxKeywords: 50},
		Debug:    DebugConfig{LLMLogging: false},
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
	if v := os.Getenv("MYNEXUS_DEBUG_LLM_LOGGING"); v != "" {
		if b, err := strconv.ParseBool(v); err == nil {
			cfg.Debug.LLMLogging = b
		}
	}

	cfg.Port = cfg.Server.Port
	return cfg
}

// FilePath returns the config.yaml path Load() would read (MYNEXUS_CONFIG_PATH
// or the default), for callers that need to read/write the file directly —
// see system_settings.go.
func FilePath() string {
	path := os.Getenv("MYNEXUS_CONFIG_PATH")
	if path == "" {
		path = "./config/config.yaml"
	}
	return path
}

// LoadFromFile reads config.yaml with no environment variable overrides
// applied, unlike Load(). Used by the system settings save flow so that
// env-injected values (e.g. a Docker Compose secret) never get baked into
// the on-disk file as a side effect of saving unrelated settings — the
// server/auth sections in particular are round-tripped from exactly what's
// on disk, not from the possibly-env-overridden in-memory Config.
func LoadFromFile() (Config, error) {
	cfg := defaults()
	data, err := os.ReadFile(FilePath())
	if err != nil {
		return cfg, err
	}
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return cfg, err
	}
	return cfg, nil
}

// SaveToFile re-serializes the whole Config struct as config.yaml. This is a
// full rewrite (not a partial/in-place edit), so hand-written comments in the
// existing file are lost — a deliberate simplicity/robustness trade-off for
// the system settings page (see docs/部署说明.md).
func SaveToFile(cfg Config) error {
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return err
	}
	return os.WriteFile(FilePath(), data, 0o644)
}
