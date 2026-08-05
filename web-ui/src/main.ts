import { createApp } from "vue";
import { createPinia } from "pinia";
import "./style.css";
import App from "./App.vue";
import { router } from "./router";
import { i18n } from "./i18n";
import { useThemeStore } from "./stores/theme";

const pinia = createPinia();
const app = createApp(App).use(pinia).use(router).use(i18n);

// Set data-theme before mount so the first paint already matches the saved
// preference instead of flashing the OS default and then swapping.
useThemeStore().init();

app.mount("#app");
