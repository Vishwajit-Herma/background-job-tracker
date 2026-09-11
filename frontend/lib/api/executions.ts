import { apiClient } from "./client";
import { Job } from "./jobs";

export interface PaginatedResponse<T> {
  data: T[];
  page: number;
  limit: number;
  totalPages: number;
  totalItems: number;
}

export interface Execution {
  id: number;
  job: number | Job;
  external_id: string;
  status: "pending" | "running" | "success" | "failed" | "retry" | "cancelled";
  last_event_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  framework: string;
  queue: string;
  worker: string;
  retry_count: number;
  error_type: string;
  error_message: string;
  traceback: string;
  metadata: any;
  created_at: string;
  updated_at: string;
}

export interface ExecutionEvent {
  id: number;
  execution: number;
  event_id: string;
  status: string;
  event_timestamp: string;
  received_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  queue: string;
  worker: string;
  retry_count: number;
  error_type: string;
  error_message: string;
  traceback: string;
  metadata: any;
}

export async function getExecutions(
  jobId?: number,
  filters: { page?: number; search?: string; ordering?: string; status?: string } = {}
): Promise<PaginatedResponse<Execution>> {
  const searchParams = new URLSearchParams();
  if (jobId) searchParams.append("job", jobId.toString());
  if (filters.page) searchParams.append("page", filters.page.toString());
  if (filters.search) searchParams.append("search", filters.search);
  if (filters.ordering) searchParams.append("ordering", filters.ordering);
  if (filters.status && filters.status !== "all") searchParams.append("status", filters.status);
  
  const query = searchParams.toString();
  const url = query ? `/executions/?${query}` : "/executions/";
  const { data } = await apiClient.get(url);
  return {
    data: data.data ?? [],
    page: data.page ?? 1,
    limit: data.limit ?? 10,
    totalPages: data.totalPages ?? 1,
    totalItems: data.totalItems ?? 0,
  };
}

export async function getExecutionEvents(executionId: number): Promise<ExecutionEvent[]> {
  const { data } = await apiClient.get(`/executions/${executionId}/events/`);
  return data.data ?? [];
}

export async function cancelExecution(executionId: number): Promise<Execution> {
  const { data } = await apiClient.post(`/executions/${executionId}/cancel/`);
  return data.data ?? data;
}
