import { apiClient } from "./client";

export interface Keyword {
  term: string;
  weight: number;
}

export interface Book {
  id: string;
  title: string;
  author: string;
  publisher: string;
  language: string;
  source_format: string;
  status: string;
  tags: string[];
  category: string;
  summary: string;
  // Whole-book content keywords extracted from chapter summaries (see
  // worker/src/pipelines/summary.py) — distinct from tags (user-/MyBooks-
  // assigned labels). Sorted by weight descending, already truncated to the
  // system's max_keywords setting server-side.
  keywords: Keyword[];
  // "" if the book has no cover yet, otherwise a path relative to
  // apiClient's base URL (see core-api's BookHandler.Cover / dto.NewBookResponse) —
  // never a raw filesystem path or the original cover_url given at import.
  cover_url: string;
  created_at: string;
  updated_at: string;
}

export interface Chapter {
  id: string;
  title: string;
  level: number;
  sort_order: number;
  summary: string;
}

export interface BookDetail extends Book {
  chapters: Chapter[];
}

export interface BookListResponse {
  items: Book[];
  total: number;
  page: number;
  size: number;
}

export async function listBooks(params: { page?: number; size?: number; status?: string; q?: string } = {}) {
  const { data } = await apiClient.get<BookListResponse>("/books", { params });
  return data;
}

export async function getBook(id: string) {
  const { data } = await apiClient.get<BookDetail>(`/books/${id}`);
  return data;
}

export interface UpdateBookRequest {
  title: string;
  author: string;
  category: string;
  tags: string[];
  language: string;
}

// PUT /books/{id} overwrites title/author/category/tags wholesale (no
// server-side merge) — callers that only want to change one field (e.g.
// the language editor in BookDetailView.vue) must send the book's current
// values for the rest, not just the one field being edited.
export async function updateBook(id: string, body: UpdateBookRequest) {
  const { data } = await apiClient.put<Book>(`/books/${id}`, body);
  return data;
}

// PUT /books/{id}/summary — a dedicated endpoint (distinct from updateBook
// above) so a manual wording tweak to the generated summary can't clobber
// title/author/category/tags/language in the same request.
export async function updateBookSummary(id: string, summary: string) {
  const { data } = await apiClient.put<Book>(`/books/${id}/summary`, { summary });
  return data;
}

export async function deleteBook(id: string) {
  await apiClient.delete(`/books/${id}`);
}

export async function rebuildBook(id: string) {
  const { data } = await apiClient.post<{ task_id: string; book_id: string }>(`/books/${id}/rebuild`);
  return data;
}

export async function summarizeBook(id: string, mode: "restart" | "continue" = "restart") {
  const { data } = await apiClient.post<{ task_id: string; book_id: string }>(`/books/${id}/summarize`, null, {
    params: { mode },
  });
  return data;
}

export interface BulkResultItem {
  id: string;
  ok: boolean;
  error?: string;
}

export async function bulkDeleteBooks(ids: string[]) {
  const { data } = await apiClient.post<{ items: BulkResultItem[] }>("/books/bulk-delete", { ids });
  return data.items;
}

export async function bulkRebuildBooks(ids: string[]) {
  const { data } = await apiClient.post<{ items: BulkResultItem[] }>("/books/bulk-rebuild", { ids });
  return data.items;
}

export async function uploadBook(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<{ task_id: string; book_id: string }>("/books/import", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
