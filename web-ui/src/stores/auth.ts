import { defineStore } from "pinia";
import * as authApi from "../api/auth";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    username: null as string | null,
    // checked distinguishes "haven't asked the server yet" from "asked and
    // logged out" so the router guard only calls /auth/me once per app load.
    checked: false,
  }),
  getters: {
    isAuthenticated: (state) => state.username !== null,
  },
  actions: {
    async fetchMe() {
      try {
        const { username } = await authApi.me();
        this.username = username;
      } catch {
        this.username = null;
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
    },
  },
});
