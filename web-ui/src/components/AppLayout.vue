<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { SUPPORTED_LOCALES, LOCALE_LABELS, setLocale, type Locale } from "../i18n";
import { useAuthStore } from "../stores/auth";
import { useAppConfigStore } from "../stores/appConfig";
import { useThemeStore } from "../stores/theme";
import AppIcon from "./AppIcon.vue";
import packageJson from "../../package.json";

const { t, locale } = useI18n();
const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const appConfig = useAppConfigStore();
const theme = useThemeStore();

const DRAWER_STORAGE_KEY = "mynexus_drawer_collapsed";
const drawerCollapsed = ref(localStorage.getItem(DRAWER_STORAGE_KEY) === "1");
const langMenuOpen = ref(false);
const appVersion = (packageJson as { version: string }).version;
const year = new Date().getFullYear();

const navItems = [
  { to: "/", name: "dashboard", icon: "dashboard" as const },
  { to: "/books", name: "books", icon: "books" as const },
  { to: "/tasks", name: "tasks", icon: "tasks" as const },
  { to: "/tokens", name: "tokens", icon: "tokens" as const },
  { to: "/chat", name: "chat", icon: "chat" as const, requiresChat: true },
  { to: "/audit-log", name: "auditLog", icon: "auditLog" as const },
];

// The "设置" (settings) drawer entry is a group with two children rather
// than a single link — mirrors the v-list-group pattern in MyBooks'
// AppHeader.vue (reader/mybooks/app/src/components/AppHeader.vue), minus
// Vuetify since this app has no UI kit dependency.
const settingsChildren = [
  { to: "/settings/system", labelKey: "settings.systemConfig" },
  { to: "/settings/account", labelKey: "settings.adminAccount" },
];
const isSettingsRoute = computed(() => route.path.startsWith("/settings"));
const SETTINGS_EXPANDED_KEY = "mynexus_settings_expanded";
const settingsExpanded = ref(
  localStorage.getItem(SETTINGS_EXPANDED_KEY) === "1" || isSettingsRoute.value,
);

function toggleSettingsGroup() {
  if (drawerCollapsed.value) {
    // Collapsed (icon-only) drawer has no room to show children — expand the
    // drawer itself first, same as MyBooks' handleMiniVariantGroupClick.
    drawerCollapsed.value = false;
    localStorage.setItem(DRAWER_STORAGE_KEY, "0");
    settingsExpanded.value = true;
  } else {
    settingsExpanded.value = !settingsExpanded.value;
  }
  localStorage.setItem(SETTINGS_EXPANDED_KEY, settingsExpanded.value ? "1" : "0");
}

onMounted(() => {
  if (!appConfig.loaded) appConfig.load();
});

function toggleDrawer() {
  drawerCollapsed.value = !drawerCollapsed.value;
  localStorage.setItem(DRAWER_STORAGE_KEY, drawerCollapsed.value ? "1" : "0");
}

function onLocaleSelect(l: Locale) {
  setLocale(l);
  langMenuOpen.value = false;
}

async function onLogout() {
  await auth.logout();
  router.push({ name: "login" });
}
</script>

<template>
  <div class="shell" :class="{ 'drawer-collapsed': drawerCollapsed }">
    <header class="app-bar">
      <div class="app-bar-start">
        <button
          class="icon-btn"
          type="button"
          :title="t('header.toggleDrawer')"
          :aria-label="t('header.toggleDrawer')"
          @click="toggleDrawer"
        >
          <span class="menu-emoji" aria-hidden="true">🕸️</span>
        </button>
      </div>
      <div class="app-bar-end">
        <button
          class="icon-btn"
          type="button"
          :title="t('header.toggleTheme')"
          :aria-label="t('header.toggleTheme')"
          @click="theme.toggle"
        >
          <AppIcon :name="theme.mode === 'dark' ? 'moon' : 'sun'" />
        </button>

        <div class="lang-menu">
          <button
            class="icon-btn"
            type="button"
            :title="t('header.language')"
            :aria-label="t('header.language')"
            @click="langMenuOpen = !langMenuOpen"
          >
            <AppIcon name="language" />
          </button>
          <div v-if="langMenuOpen" class="lang-dropdown" @mouseleave="langMenuOpen = false">
            <button
              v-for="l in SUPPORTED_LOCALES"
              :key="l"
              type="button"
              class="lang-option"
              :class="{ active: l === locale }"
              @click="onLocaleSelect(l)"
            >
              {{ LOCALE_LABELS[l] }}
            </button>
          </div>
        </div>

        <span class="username">{{ auth.username }}</span>

        <button
          class="icon-btn"
          type="button"
          :title="t('nav.logout')"
          :aria-label="t('nav.logout')"
          @click="onLogout"
        >
          <AppIcon name="logout" />
        </button>
      </div>
    </header>

    <div class="body">
      <aside class="drawer">
        <nav>
          <router-link
            v-for="item in navItems"
            v-show="!item.requiresChat || appConfig.chatEnabled"
            :key="item.name"
            :to="item.to"
            class="nav-item"
            :title="drawerCollapsed ? t(`nav.${item.name}`) : undefined"
          >
            <AppIcon :name="item.icon" />
            <span class="nav-label">{{ t(`nav.${item.name}`) }}</span>
          </router-link>

          <button
            type="button"
            class="nav-item nav-group-header"
            :class="{ 'router-link-exact-active': isSettingsRoute }"
            :title="drawerCollapsed ? t('nav.settings') : undefined"
            @click="toggleSettingsGroup"
          >
            <AppIcon name="settings" />
            <span class="nav-label">{{ t("nav.settings") }}</span>
            <AppIcon
              v-if="!drawerCollapsed"
              name="chevronLeft"
              :size="16"
              class="chevron"
              :class="{ expanded: settingsExpanded }"
            />
          </button>
          <div v-show="settingsExpanded && !drawerCollapsed" class="nav-group-children">
            <router-link
              v-for="child in settingsChildren"
              :key="child.to"
              :to="child.to"
              class="nav-item nav-child"
            >
              <span class="nav-label">{{ t(child.labelKey) }}</span>
            </router-link>
          </div>
        </nav>
      </aside>

      <main class="content">
        <router-view />
      </main>
    </div>

    <footer class="app-footer">
      <span>{{ t("footer.name") }} v{{ appVersion }}</span>
      <span>© {{ year }} PoxenStudio</span>
    </footer>
  </div>
</template>

<style scoped>
.shell {
  --app-bar-height: 56px;
  --drawer-width: 220px;
  --drawer-width-collapsed: 64px;
  --footer-height: 40px;

  min-height: 100svh;
  display: flex;
  flex-direction: column;
}

/* App bar (top) */
.app-bar {
  height: var(--app-bar-height);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0 1rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  box-shadow: var(--elevation-1);
  position: sticky;
  top: 0;
  z-index: 20;
}
.app-bar-start,
.app-bar-end {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.username {
  font-size: 0.85rem;
  opacity: 0.75;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  transition: background-color 0.15s ease;
}
.icon-btn:hover {
  background: var(--surface-hover);
}
.icon-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.menu-emoji {
  font-size: 20px;
  line-height: 1;
}

/* Language dropdown */
.lang-menu {
  position: relative;
}
.lang-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  min-width: 96px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--elevation-2);
  padding: 0.25rem;
  display: flex;
  flex-direction: column;
  z-index: 30;
}
.lang-option {
  border: none;
  background: transparent;
  color: inherit;
  text-align: left;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}
.lang-option:hover {
  background: var(--surface-hover);
}
.lang-option.active {
  color: var(--accent);
  font-weight: 600;
  background: var(--accent-bg);
}

/* Body: drawer + content */
.body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.drawer {
  width: var(--drawer-width);
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 0.75rem 0.5rem;
  transition: width 0.18s ease;
  overflow-x: hidden;
  position: sticky;
  top: var(--app-bar-height);
  align-self: flex-start;
  height: calc(100svh - var(--app-bar-height) - var(--footer-height));
}
.shell.drawer-collapsed .drawer {
  width: var(--drawer-width-collapsed);
}

.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem 0.25rem 1rem;
  margin-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
  text-align: center;
}
.brand-mark {
  font-size: 1.75rem;
  line-height: 1;
}
.brand-name {
  font-weight: 600;
  font-size: 1rem;
  color: var(--text-h);
  white-space: nowrap;
}
.shell.drawer-collapsed .brand-name {
  display: none;
}

nav {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  border-radius: 20px;
  color: var(--text);
  text-decoration: none;
  white-space: nowrap;
  font-size: 0.9rem;
}
.nav-item:hover {
  background: var(--surface-hover);
}
.nav-item.router-link-exact-active {
  background: rgba(120, 120, 128, 0.55);
  color: #fff;
  font-weight: 600;
}
.shell.drawer-collapsed .nav-label {
  display: none;
}

.nav-group-header {
  width: 100%;
  border: none;
  background: transparent;
  font: inherit;
  cursor: pointer;
}
.chevron {
  margin-left: auto;
  flex-shrink: 0;
  transform: rotate(180deg);
  transition: transform 0.15s ease;
}
.chevron.expanded {
  transform: rotate(270deg);
}
.nav-group-children {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.nav-child {
  padding-left: 2.5rem;
  font-size: 0.85rem;
}

.content {
  flex: 1;
  min-width: 0;
  padding: 1.5rem 2rem;
}

/* Footer */
.app-footer {
  height: var(--footer-height);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  padding: 0 1rem;
  font-size: 0.78rem;
  opacity: 0.65;
  border-top: 1px solid var(--border);
  background: var(--surface);
}

@media (max-width: 720px) {
  .drawer {
    position: fixed;
    left: 0;
    z-index: 15;
    box-shadow: var(--elevation-2);
  }
  .shell:not(.drawer-collapsed) .drawer {
    width: var(--drawer-width);
  }
  .shell.drawer-collapsed .drawer {
    width: 0;
    padding-left: 0;
    padding-right: 0;
    border-right: none;
  }
  .username {
    display: none;
  }
}
</style>
