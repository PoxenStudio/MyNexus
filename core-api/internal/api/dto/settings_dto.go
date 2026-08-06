package dto

import "mynexus/core-api/internal/config"

// SystemSettings is every config.yaml section except server/auth (those two
// hold the listen port/CORS and the JWT secret — process-identity/security
// values edited by hand or via deploy-time env vars, not from the web UI).
// Both GET and PUT /api/v1/system/settings use this shape.
type SystemSettings struct {
	Storage   config.StorageConfig   `json:"storage"`
	Worker    config.WorkerConfig    `json:"worker"`
	Embedding config.EmbeddingConfig `json:"embedding"`
	LLM       config.LLMConfig       `json:"llm"`
	Splitter  config.SplitterConfig  `json:"splitter"`
	I18n      config.I18nConfig      `json:"i18n"`
	Chat      config.ChatConfig      `json:"chat"`
	Keyword   config.KeywordConfig   `json:"keyword"`
	Debug     config.DebugConfig     `json:"debug"`
}
