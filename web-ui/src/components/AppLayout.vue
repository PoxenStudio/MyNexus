<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { SUPPORTED_LOCALES, setLocale, type Locale } from "../i18n";

const { t, locale } = useI18n();

function onLocaleChange(e: Event) {
  setLocale((e.target as HTMLSelectElement).value as Locale);
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
      </nav>
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
.locale-select {
  margin-top: auto;
  padding: 0.4rem;
}
.content {
  flex: 1;
  padding: 1.5rem 2rem;
  min-width: 0;
}
</style>
