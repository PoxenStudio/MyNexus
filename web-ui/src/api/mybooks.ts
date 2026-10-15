import { apiClient } from "./client";

export interface MyBooksFileInfo {
  format: string;
  size: number;
}

export interface MyBooksSearchItem {
  id: number;
  title: string;
  author: string;
  authors: string[];
  thumb: string;
  img: string;
  publisher: string;
  language: string;
  tags: string[];
  series: string;
  isbn: string;
  pubdate: string;
  comments: string;
  files: MyBooksFileInfo[];
}

export interface MyBooksSearchResponse {
  title: string;
  total: number;
  start: number;
  size: number;
  books: MyBooksSearchItem[];
}

export interface MyBooksTestRequest {
  base_url: string;
  username: string;
  password: string;
}

export interface MyBooksTestResult {
  ok: boolean;
  error?: string;
}

export interface MyBooksImportRequest {
  mybooks_id: number;
  format: string;
}

export interface MyBooksImportResponse {
  book_id: string;
  task_id: string;
}

export async function testMyBooksConnection(req: MyBooksTestRequest): Promise<MyBooksTestResult> {
  const { data } = await apiClient.post<MyBooksTestResult>("/mybooks/test", req);
  return data;
}

export async function searchMyBooks(name: string, start = 0, size = 20): Promise<MyBooksSearchResponse> {
  const { data } = await apiClient.get<MyBooksSearchResponse>("/mybooks/search", {
    params: { name, start, size },
  });
  return data;
}

export async function importFromMyBooks(mybooksId: number, format: string, coverUrl?: string): Promise<MyBooksImportResponse> {
  const { data } = await apiClient.post<MyBooksImportResponse>(
    `/mybooks/import${coverUrl ? `?cover_url=${encodeURIComponent(coverUrl)}` : ""}`,
    { mybooks_id: mybooksId, format },
  );
  return data;
}
