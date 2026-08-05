import { defineStore } from "pinia";

export type ThemeMode = "light" | "dark";

const STORAGE_KEY = "mynexus_theme";

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function detectInitial(): ThemeMode {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return systemPrefersDark() ? "dark" : "light";
}

// Drives the `data-theme` attribute on <html>, which style.css keys its
// light/dark variable overrides off (in addition to the prefers-color-scheme
// fallback for the very first paint, before this store has a chance to run).
export const useThemeStore = defineStore("theme", {
  state: () => ({
    mode: detectInitial() as ThemeMode,
  }),
  actions: {
    apply() {
      document.documentElement.setAttribute("data-theme", this.mode);
    },
    // Call once at startup so the attribute is set before the app mounts.
    init() {
      this.apply();
    },
    toggle() {
      this.mode = this.mode === "dark" ? "light" : "dark";
      localStorage.setItem(STORAGE_KEY, this.mode);
      this.apply();
    },
  },
});
