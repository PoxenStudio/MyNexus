import { apiClient } from "./client";

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

export async function deleteBook(id: string) {
  await apiClient.delete(`/books/${id}`);
}

export async function rebuildBook(id: string) {
  const { data } = await apiClient.post<{ task_id: string; book_id: string }>(`/books/${id}/rebuild`);
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
