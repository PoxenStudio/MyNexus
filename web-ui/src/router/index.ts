import { createRouter, createWebHistory } from "vue-router";
import AppLayout from "../components/AppLayout.vue";
import LoginView from "../views/LoginView.vue";
import DashboardView from "../views/admin/DashboardView.vue";
import BooksListView from "../views/admin/BooksListView.vue";
import BookDetailView from "../views/admin/BookDetailView.vue";
import TasksView from "../views/admin/TasksView.vue";
import TokensView from "../views/admin/TokensView.vue";
import SettingsView from "../views/admin/SettingsView.vue";
import ChatView from "../views/ChatView.vue";
import { useAuthStore } from "../stores/auth";
import { useAppConfigStore } from "../stores/appConfig";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    {
      path: "/",
      component: AppLayout,
      children: [
        { path: "", name: "dashboard", component: DashboardView },
        { path: "books", name: "books", component: BooksListView },
        { path: "books/:id", name: "book-detail", component: BookDetailView },
        { path: "tasks", name: "tasks", component: TasksView },
        { path: "tokens", name: "tokens", component: TokensView },
        { path: "settings", name: "settings", component: SettingsView },
        { path: "chat", name: "chat", component: ChatView, meta: { requiresChat: true } },
      ],
    },
  ],
});

// Every route except /login requires a logged-in admin session; the /chat
// route additionally requires the config.chat.enabled feature toggle (see
// core-api's GET /system/config) to be on.
router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.checked) {
    await auth.fetchMe();
  }

  if (to.name !== "login" && !auth.isAuthenticated) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && auth.isAuthenticated) {
    return { name: "dashboard" };
  }

  if (to.meta.requiresChat) {
    const appConfig = useAppConfigStore();
    if (!appConfig.loaded) {
      await appConfig.load();
    }
    if (!appConfig.chatEnabled) {
      return { name: "dashboard" };
    }
  }

  return true;
});
