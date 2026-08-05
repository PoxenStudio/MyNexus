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

export async function listTasks(params: { page?: number; size?: number; status?: string } = {}) {
  const { data } = await apiClient.get<TaskListResponse>("/tasks", { params });
  return data;
}

export async function retryTask(id: string) {
  const { data } = await apiClient.post<Task>(`/tasks/${id}/retry`);
  return data;
}
