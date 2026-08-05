import { apiClient } from "./client";

export interface AuditLogEntry {
  id: string;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  detail: string;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  size: number;
}

export async function listAuditLog(params: { page?: number; size?: number } = {}) {
  const { data } = await apiClient.get<AuditLogListResponse>("/audit-log", { params });
  return data;
}
