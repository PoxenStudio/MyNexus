package config

import (
	"os"

	"gopkg.in/yaml.v3"
)

type ServerConfig struct {
	Port        string   `yaml:"port"`
	CORSOrigins []string `yaml:"cors_origins"`
}

type AuthConfig struct {
	JWTSecret   string `yaml:"jwt_secret"`
	TokenPrefix string `yaml:"token_prefix"`
}

type SQLiteConfig struct {
	Path string `yaml:"path"`
}

type StorageConfig struct {
	Database    string       `yaml:"database"`
	SQLite      SQLiteConfig `yaml:"sqlite"`
	VectorStore string       `yaml:"vector_store"`
}

type WorkerConfig struct {
	URL                 string `yaml:"url"`
	MaxConcurrentTasks  int    `yaml:"max_concurrent_tasks"`
	TaskTimeoutSeconds  int    `yaml:"task_timeout_seconds"`
}

type I18nConfig struct {
	DefaultLocale string   `yaml:"default_locale"`
	Supported     []string `yaml:"supported"`
}

type Config struct {
	Server  ServerConfig  `yaml:"server"`
	Auth    AuthConfig    `yaml:"auth"`
	Storage StorageConfig `yaml:"storage"`
	Worker  WorkerConfig  `yaml:"worker"`
	I18n    I18nConfig    `yaml:"i18n"`

	// Port kept for backward-compatible direct access; mirrors Server.Port.
	Port string
}

func defaults() Config {
	return Config{
		Server: ServerConfig{Port: "8080", CORSOrigins: []string{"*"}},
		Auth:   AuthConfig{TokenPrefix: "mnx_"},
		Storage: StorageConfig{
			Database: "sqlite",
			SQLite:   SQLiteConfig{Path: "./data/mynexus.db"},
		},
		Worker: WorkerConfig{URL: "http://localhost:8001", MaxConcurrentTasks: 1, TaskTimeoutSeconds: 600},
		I18n:   I18nConfig{DefaultLocale: "zh-CN", Supported: []string{"zh-CN", "zh-TW", "en-US"}},
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

	cfg.Port = cfg.Server.Port
	return cfg
}
