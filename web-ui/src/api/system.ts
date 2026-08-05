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
