import { defineStore } from "pinia";
import { fetchConfig } from "../api/system";

export const useAppConfigStore = defineStore("appConfig", {
  state: () => ({
    chatEnabled: true,
    loaded: false,
  }),
  actions: {
    async load() {
      try {
        const cfg = await fetchConfig();
        this.chatEnabled = cfg.chat_enabled;
      } finally {
        this.loaded = true;
      }
    },
  },
});
