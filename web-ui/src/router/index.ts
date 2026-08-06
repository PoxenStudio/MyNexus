import { createRouter, createWebHistory } from "vue-router";
import AppLayout from "../components/AppLayout.vue";
import LoginView from "../views/LoginView.vue";
import DashboardView from "../views/admin/DashboardView.vue";
import BooksListView from "../views/admin/BooksListView.vue";
import BookDetailView from "../views/admin/BookDetailView.vue";
import TasksView from "../views/admin/TasksView.vue";
import TokensView from "../views/admin/TokensView.vue";
import SystemConfigView from "../views/admin/SystemConfigView.vue";
import AdminAccountView from "../views/admin/AdminAccountView.vue";
import AuditLogView from "../views/admin/AuditLogView.vue";
import UsersView from "../views/admin/UsersView.vue";
import ChatView from "../views/ChatView.vue";
import { useAuthStore } from "../stores/auth";
import { useAppConfigStore } from "../stores/appConfig";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { titleKey: "login.title" } },
    {
      path: "/",
      component: AppLayout,
      children: [
        {
          path: "",
          name: "dashboard",
          component: DashboardView,
          meta: { requiresAdmin: true, titleKey: "nav.dashboard" },
        },
        {
          path: "books",
          name: "books",
          component: BooksListView,
          meta: { requiresAdmin: true, titleKey: "nav.books" },
        },
        {
          path: "books/:id",
          name: "book-detail",
          component: BookDetailView,
          meta: { requiresAdmin: true, titleKey: "books.detail" },
        },
        {
          path: "tasks",
          name: "tasks",
          component: TasksView,
          meta: { requiresAdmin: true, titleKey: "nav.tasks" },
        },
        {
          path: "tokens",
          name: "tokens",
          component: TokensView,
          meta: { requiresAdmin: true, titleKey: "nav.tokens" },
        },
        {
          path: "audit-log",
          name: "audit-log",
          component: AuditLogView,
          meta: { requiresAdmin: true, titleKey: "nav.auditLog" },
        },
        { path: "settings", redirect: "/settings/system" },
        {
          path: "settings/system",
          name: "settings-system",
          component: SystemConfigView,
          meta: { requiresAdmin: true, titleKey: "settings.systemConfig" },
        },
        {
          path: "settings/users",
          name: "settings-users",
          component: UsersView,
          meta: { requiresAdmin: true, titleKey: "settings.users" },
        },
        {
          // Both roles land here — it's "个人信息" (own password/avatar),
          // not admin-only. The name predates multi-user; kept as-is so
          // existing bookmarks/links to /settings/account keep working.
          path: "settings/account",
          name: "settings-account",
          component: AdminAccountView,
          meta: { titleKey: "settings.adminAccount" },
        },
        {
          path: "chat",
          name: "chat",
          component: ChatView,
          meta: { requiresChat: true, titleKey: "nav.chat" },
        },
      ],
    },
  ],
});

// Every route except /login requires a logged-in session. Routes flagged
// requiresAdmin are the back-office surface (dashboard, books, tasks,
// tokens, audit log, system config, user management) — a plain "user" role
// account is bounced to /chat instead (its only other page besides its own
// profile). The /chat route additionally requires the config.chat.enabled
// feature toggle (see core-api's GET /system/config) to be on.
router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.checked) {
    await auth.fetchMe();
  }

  if (to.name !== "login" && !auth.isAuthenticated) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && auth.isAuthenticated) {
    return { name: auth.isAdmin ? "dashboard" : "chat" };
  }

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: "chat" };
  }

  if (to.meta.requiresChat) {
    const appConfig = useAppConfigStore();
    if (!appConfig.loaded) {
      await appConfig.load();
    }
    if (!appConfig.chatEnabled) {
      // A "user" role account has nowhere else to go but its own profile if
      // chat is turned off — an admin falls back to the dashboard.
      return { name: auth.isAdmin ? "dashboard" : "settings-account" };
    }
  }

  return true;
});
