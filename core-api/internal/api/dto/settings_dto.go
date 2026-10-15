package dto

import "mynexus/core-api/internal/config"

// SystemSettings is every config.yaml section except server/auth (process and
// authentication settings are managed outside the system settings page).
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
	Retrieval config.RetrievalConfig `json:"retrieval"`
	Debug     config.DebugConfig     `json:"debug"`
	Summary   config.SummaryConfig   `json:"summary"`
	MyBooks   config.MyBooksConfig   `json:"mybooks"`
}
