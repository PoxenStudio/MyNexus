import { apiClient } from "./client";

export async function login(username: string, password: string) {
  const { data } = await apiClient.post<{ username: string }>("/auth/login", { username, password });
  return data;
}

export async function logout() {
  await apiClient.post("/auth/logout");
}

export async function me() {
  const { data } = await apiClient.get<{ username: string; avatar_url: string }>("/auth/me");
  return data;
}

export async function changePassword(oldPassword: string, newPassword: string) {
  await apiClient.post("/auth/change-password", { old_password: oldPassword, new_password: newPassword });
}

export async function uploadAvatar(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<{ avatar_url: string }>("/auth/avatar", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
