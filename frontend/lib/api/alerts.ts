import { apiClient } from "./client";

export interface AlertRule {
  id: number;
  project: number;
  job: number | null;
  metric: "FAILURE_RATE" | "RETRY_RATE" | "P95_DURATION";
  threshold: number;
  window_minutes: number;
  severity: "DEGRADED" | "CRITICAL";
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateAlertRulePayload {
  project: number;
  job?: number | null;
  metric: "FAILURE_RATE" | "RETRY_RATE" | "P95_DURATION";
  threshold: number;
  window_minutes: number;
  severity: "DEGRADED" | "CRITICAL";
  is_active?: boolean;
}

export interface UpdateAlertRulePayload extends Partial<CreateAlertRulePayload> {}

export interface PaginatedAlertRules {
  data: AlertRule[];
  page: number;
  totalPages: number;
  totalItems: number;
}

interface AlertRuleFilters {
  project?: number;
  job?: number;
  page?: number;
  search?: string;
  ordering?: string;
}

export async function getPaginatedAlertRules(filters: AlertRuleFilters = {}): Promise<PaginatedAlertRules> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.append(key, value.toString());
    }
  });

  const res = await apiClient.get<any>(`/alerts/rules/?${params.toString()}`);
  const payload = res.data;
  return {
    data: Array.isArray(payload.data) ? payload.data : Array.isArray(payload) ? payload : [],
    page: payload.page ?? 1,
    totalPages: payload.totalPages ?? 1,
    totalItems: payload.totalItems ?? 0,
  };
}

export async function getAlertRules(projectId?: number, jobId?: number): Promise<AlertRule[]> {
  const params = new URLSearchParams();
  if (projectId) params.append("project", projectId.toString());
  if (jobId) params.append("job", jobId.toString());

  const response = await apiClient.get<any>(`/alerts/rules/?${params.toString()}`);
  const data = response.data?.data ?? response.data;
  return Array.isArray(data) ? data : [];
}

export async function getAlertRule(id: number): Promise<AlertRule> {
  const response = await apiClient.get<any>(`/alerts/rules/${id}/`);
  return response.data?.data ?? response.data;
}

export async function createAlertRule(data: CreateAlertRulePayload): Promise<AlertRule> {
  const response = await apiClient.post<any>("/alerts/rules/", data);
  return response.data?.data ?? response.data;
}

export async function updateAlertRule(id: number, data: UpdateAlertRulePayload): Promise<AlertRule> {
  const response = await apiClient.patch<any>(`/alerts/rules/${id}/`, data);
  return response.data?.data ?? response.data;
}

export async function deleteAlertRule(id: number): Promise<void> {
  await apiClient.delete(`/alerts/rules/${id}/`);
}
