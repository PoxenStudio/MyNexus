import { defineStore } from "pinia";
import * as authApi from "../api/auth";
import { apiClient } from "../api/client";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    username: null as string | null,
    avatarUrl: "" as string,
    // checked distinguishes "haven't asked the server yet" from "asked and
    // logged out" so the router guard only calls /auth/me once per app load.
    checked: false,
  }),
  getters: {
    isAuthenticated: (state) => state.username !== null,
    // avatarUrl from the server is API-relative ("/auth/avatar/{id}"); the
    // <img> tag needs the full path including the /api/v1 base.
    fullAvatarUrl: (state) => (state.avatarUrl ? apiClient.defaults.baseURL + state.avatarUrl : ""),
  },
  actions: {
    async fetchMe() {
      try {
        const { username, avatar_url } = await authApi.me();
        this.username = username;
        this.avatarUrl = avatar_url;
      } catch {
        this.username = null;
        this.avatarUrl = "";
      } finally {
        this.checked = true;
      }
    },
    async login(username: string, password: string) {
      const result = await authApi.login(username, password);
      this.username = result.username;
      this.checked = true;
    },
    async logout() {
      await authApi.logout();
      this.username = null;
      this.avatarUrl = "";
    },
    async uploadAvatar(file: File) {
      const { avatar_url } = await authApi.uploadAvatar(file);
      // Cache-bust: the URL itself is stable per admin, but the served bytes
      // just changed — force the <img> to refetch instead of showing a
      // browser-cached copy at the same URL.
      this.avatarUrl = `${avatar_url}?t=${Date.now()}`;
    },
  },
});
