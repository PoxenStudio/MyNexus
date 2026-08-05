import { apiClient } from "./client";

export async function login(username: string, password: string) {
  const { data } = await apiClient.post<{ username: string }>("/auth/login", { username, password });
  return data;
}

export async function logout() {
  await apiClient.post("/auth/logout");
}

export async function me() {
  const { data } = await apiClient.get<{ username: string }>("/auth/me");
  return data;
}

export async function changePassword(oldPassword: string, newPassword: string) {
  await apiClient.post("/auth/change-password", { old_password: oldPassword, new_password: newPassword });
}
