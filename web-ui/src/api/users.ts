import { apiClient } from "./client";

export interface AppUser {
  id: string;
  username: string;
  nickname: string;
  role: "admin" | "user";
  status: "active" | "disabled";
  avatar_url: string;
  last_login_at: string;
  created_at: string;
}

export async function listUsers() {
  const { data } = await apiClient.get<{ users: AppUser[] }>("/users");
  return data.users;
}

export async function createUser(username: string, nickname: string, password: string, role: string) {
  const { data } = await apiClient.post<AppUser>("/users", { username, nickname, password, role });
  return data;
}

export async function setUserRole(id: string, role: string) {
  await apiClient.put(`/users/${id}/role`, { role });
}

export async function setUserStatus(id: string, status: "active" | "disabled") {
  await apiClient.put(`/users/${id}/status`, { status });
}

export async function resetUserPassword(id: string, newPassword: string) {
  await apiClient.put(`/users/${id}/password`, { new_password: newPassword });
}
