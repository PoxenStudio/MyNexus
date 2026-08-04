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
