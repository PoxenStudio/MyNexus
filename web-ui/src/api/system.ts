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
// section except server/auth (see docs/部署说明.md).
export interface ProviderSettings {
  api_key: string;
  base_url: string;
  model: string;
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
  };
  llm: {
    provider: string;
    openai: ProviderSettings;
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
  };
  debug: {
    llm_logging: boolean;
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
