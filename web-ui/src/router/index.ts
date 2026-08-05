import { createRouter, createWebHistory } from "vue-router";
import DashboardView from "../views/admin/DashboardView.vue";
import BooksListView from "../views/admin/BooksListView.vue";
import BookDetailView from "../views/admin/BookDetailView.vue";
import TasksView from "../views/admin/TasksView.vue";
import TokensView from "../views/admin/TokensView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "dashboard", component: DashboardView },
    { path: "/books", name: "books", component: BooksListView },
    { path: "/books/:id", name: "book-detail", component: BookDetailView },
    { path: "/tasks", name: "tasks", component: TasksView },
    { path: "/tokens", name: "tokens", component: TokensView },
  ],
});
