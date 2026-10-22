import { apiClient } from "./client";

export interface SystemHealth {
  status: string;
  service: string;
  database?: string;
}

export async function fetchHealth(): Promise<SystemHealth> {
  const { data } = await apiClient.get<SystemHealth>("/system/health");
  return data;
}

export interface SystemStats {
  books_total: number;
  chunks_total: number;
  sessions_total: number;
  books_by_status: Record<string, number>;
  tasks_by_status: Record<string, number>;
}

export async function fetchStats(): Promise<SystemStats> {
  const { data } = await apiClient.get<SystemStats>("/system/stats");
  return data;
}

export interface SystemConfig {
  chat_enabled: boolean;
}

export async function fetchConfig(): Promise<SystemConfig> {
  const { data } = await apiClient.get<SystemConfig>("/system/config");
  return data;
}

// Mirrors core-api/internal/api/dto.SystemSettings — every config.yaml
// section except server/auth.
export interface ProviderSettings {
  api_key: string;
  base_url: string;
  model: string;
}

// LLM openai adds a single-chapter input cap for the summary pipeline (see
// worker's _fit_budget; 5000–50000, 0 disables). OpenAI-provider only.
export interface LLMProviderSettings extends ProviderSettings {
  chapter_token_budget: number;
}

export interface SystemSettings {
  storage: {
    database: string;
    sqlite: { path: string };
    postgres: { dsn: string };
    vector_store: string;
    vector_store_path: string;
    upload_dir: string;
  };
  worker: {
    url: string;
    max_concurrent_tasks: number;
    task_timeout_seconds: number;
  };
  embedding: {
    provider: string;
    openai: ProviderSettings;
    ollama: ProviderSettings;
    local: { model: string; model_path: string };
  };
  llm: {
    provider: string;
    openai: LLMProviderSettings;
    ollama: ProviderSettings;
  };
  splitter: {
    chunk_size: number;
    chunk_overlap: number;
    strategy: string;
  };
  i18n: {
    default_locale: string;
    supported: string[];
  };
  chat: {
    enabled: boolean;
    // Per-user cap on chat sessions (see ChatService.EnforceSessionLimit) —
    // once a user goes over this, their oldest session is silently pruned
    // on their next new conversation. <= 0 means no limit.
    max_sessions: number;
    sliding_window_size: number;
    memory_enabled: boolean;
    return_citations: boolean;
  };
  keyword: {
    max_keywords: number;
  };
  retrieval: {
    fusion: string;
    vector_weight: number;
    keyword_weight: number;
  };
  debug: {
    llm_logging: boolean;
  };
  summary: {
    // When true (the default), the EPUB/TXT parsers drop chapters whose
    // cleaned title is an index/bibliography heading instead of
    // ingesting/summarizing them (see worker/src/util/chapter_title.py).
    skip_backmatter_chapters: boolean;
  };
  mybooks: {
    base_url: string;
    username: string;
    password: string;
  };
}

export async function fetchSettings(): Promise<SystemSettings> {
  const { data } = await apiClient.get<SystemSettings>("/system/settings");
  return data;
}

// Rewrites config.yaml and restarts both core-api and worker (best-effort —
// see the proto comment on WorkerService.Shutdown for what that does and
// doesn't guarantee outside Docker Compose). The response itself still
// arrives normally; core-api exits shortly after sending it.
export async function saveSettings(settings: SystemSettings): Promise<void> {
  await apiClient.put("/system/settings", settings);
}

export interface ProviderTestResult {
  ok: boolean;
  error?: string;
}

export interface ProviderTestRequest {
  provider: "embedding" | "llm";
  kind: "openai" | "ollama" | "local";
  base_url: string;
  api_key?: string;
  model?: string;
}

export async function testProvider(req: ProviderTestRequest): Promise<ProviderTestResult> {
  const { data } = await apiClient.post<ProviderTestResult>("/system/test-provider", req);
  return data;
}
