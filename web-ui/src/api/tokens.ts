import { apiClient } from "./client";

export interface ApiToken {
  id: string;
  alias: string;
  masked_token: string;
  last_used_at: string;
  is_revoked: boolean;
  created_at: string;
}

export async function listTokens() {
  const { data } = await apiClient.get<{ items: ApiToken[] }>("/tokens");
  return data.items;
}

export async function createToken(alias: string) {
  const { data } = await apiClient.post<{ id: string; token: string; alias: string }>("/tokens", { alias });
  return data;
}

export async function revokeToken(id: string) {
  await apiClient.delete(`/tokens/${id}`);
}
