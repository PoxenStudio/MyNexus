import { apiClient } from "./client";

export interface StageLogEntry {
  stage: string;
  message?: string;
  progress: number;
  at: string;
}

export interface Task {
  id: string;
  book_id: string;
  type: string;
  status: string;
  progress: number;
  error_msg: string;
  // false while an ingest task is queued waiting for a free
  // worker.max_concurrent_tasks slot (see core-api's internal/dispatch) —
  // always true for a summarize task. A "pending" task with dispatched
  // false is what should be labeled "queued" rather than plain "pending".
  dispatched: boolean;
  stages_log: StageLogEntry[];
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  items: Task[];
  total: number;
  page: number;
  size: number;
}

export async function listTasks(
  params: { page?: number; size?: number; status?: string; book_id?: string } = {},
) {
  const { data } = await apiClient.get<TaskListResponse>("/tasks", { params });
  return data;
}

export async function retryTask(id: string) {
  const { data } = await apiClient.post<Task>(`/tasks/${id}/retry`);
  return data;
}

export async function getTask(id: string) {
  const { data } = await apiClient.get<Task>(`/tasks/${id}`);
  return data;
}
