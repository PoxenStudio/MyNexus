<script setup lang="ts">
import { onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { SUPPORTED_LOCALES, setLocale, type Locale } from "../i18n";
import { useAuthStore } from "../stores/auth";
import { useAppConfigStore } from "../stores/appConfig";

const { t, locale } = useI18n();
const router = useRouter();
const auth = useAuthStore();
const appConfig = useAppConfigStore();

onMounted(() => {
  if (!appConfig.loaded) appConfig.load();
});

function onLocaleChange(e: Event) {
  setLocale((e.target as HTMLSelectElement).value as Locale);
}

async function onLogout() {
  await auth.logout();
  router.push({ name: "login" });
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">🕸️ MyNexus</div>
      <nav>
        <router-link to="/">{{ t("nav.dashboard") }}</router-link>
        <router-link to="/books">{{ t("nav.books") }}</router-link>
        <router-link to="/tasks">{{ t("nav.tasks") }}</router-link>
        <router-link to="/tokens">{{ t("nav.tokens") }}</router-link>
        <router-link v-if="appConfig.chatEnabled" to="/chat">{{ t("nav.chat") }}</router-link>
        <router-link to="/audit-log">{{ t("nav.auditLog") }}</router-link>
        <router-link to="/settings">{{ t("nav.settings") }}</router-link>
      </nav>
      <div class="user-box">
        <span class="username">{{ auth.username }}</span>
        <button class="ghost" @click="onLogout">{{ t("nav.logout") }}</button>
      </div>
      <select class="locale-select" :value="locale" @change="onLocaleChange">
        <option v-for="l in SUPPORTED_LOCALES" :key="l" :value="l">{{ l }}</option>
      </select>
    </aside>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 200px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 1rem;
  gap: 1rem;
}
.brand {
  font-weight: 600;
  font-size: 1.1rem;
}
nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
nav a {
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  color: inherit;
  text-decoration: none;
}
nav a.router-link-exact-active {
  background: var(--accent-bg);
  color: var(--accent);
  font-weight: 600;
}
.user-box {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.85rem;
}
.username {
  opacity: 0.75;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
button.ghost {
  border: 1px solid var(--border);
  background: transparent;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  color: inherit;
  font-size: 0.85rem;
}
.locale-select {
  padding: 0.4rem;
}
.content {
  flex: 1;
  padding: 1.5rem 2rem;
  min-width: 0;
}
</style>
