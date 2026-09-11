import { apiClient } from "./client";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Project {
  id: number;
  team: number;
  name: string;
  description: string;
  status: "active" | "inactive" | "deleted";
  created_at: string;
  updated_at: string;
  created_by?: number;
  modified_by?: number;
  jobs_count?: number;
  executions_count?: number;
  success_rate?: number | null;
  active_incidents_count?: number;
  operational_status?: "CRITICAL" | "DEGRADED" | "HEALTHY";
}

export interface APIKey {
  id: number;
  name: string;
  key_prefix: string;
  is_revoked: boolean;
  created_at: string;
  created_by: number | null;
  revoked_at: string | null;
  revoked_by: number | null;
}

export interface APIKeyCreated extends APIKey {
  key: string; // The raw key — only returned once on creation
}

// ─── Projects ─────────────────────────────────────────────────────────────────

export interface PaginatedProjects {
  data: Project[];
  page: number;
  totalPages: number;
  totalItems: number;
}

export interface ProjectFilters {
  team?: number;
  status?: string;
  search?: string;
  ordering?: string;
  page?: number;
  limit?: number;
}

export async function getProjectsPaginated(filters: ProjectFilters = {}): Promise<PaginatedProjects> {
  const params: Record<string, string | number> = {};
  if (filters.team) params.team = filters.team;
  if (filters.status) params.status = filters.status;
  if (filters.search) params.search = filters.search;
  if (filters.ordering) params.ordering = filters.ordering;
  if (filters.page) params.page = filters.page;
  if (filters.limit) params.limit = filters.limit;

  const { data } = await apiClient.get<any>("/projects/", { params });
  return {
    data: Array.isArray(data?.data) ? data.data : Array.isArray(data) ? data : [],
    page: data?.page ?? 1,
    totalPages: data?.totalPages ?? 1,
    totalItems: data?.totalItems ?? 0,
  };
}

export async function getProjects(
  teamId?: number, 
  filters: { search?: string; ordering?: string } = {}
): Promise<Project[]> {
  const params: Record<string, string | number> = { no_pagination: "true" };
  if (teamId) params.team = teamId;
  if (filters.search) params.search = filters.search;
  if (filters.ordering) params.ordering = filters.ordering;
  
  const { data } = await apiClient.get<any>("/projects/", { params });
  return Array.isArray(data?.data) ? data.data : Array.isArray(data) ? data : [];
}

export async function getProject(projectId: number): Promise<Project> {
  const { data } = await apiClient.get<{ data: Project }>(`/projects/${projectId}/`);
  return (data as any).data ?? data;
}

export async function createProject(payload: {
  team: number;
  name: string;
  description?: string;
}): Promise<Project> {
  const { data } = await apiClient.post<{ data: Project }>("/projects/", payload);
  return (data as any).data ?? data;
}

export async function updateProject(
  projectId: number,
  payload: { name?: string; description?: string; status?: "active" | "inactive" }
): Promise<Project> {
  const { data } = await apiClient.patch<{ data: Project }>(`/projects/${projectId}/`, payload);
  return (data as any).data ?? data;
}

export async function deleteProject(projectId: number): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/`);
}

// ─── API Keys ─────────────────────────────────────────────────────────────────

export async function getAPIKeys(projectId: number): Promise<APIKey[]> {
  const { data } = await apiClient.get<{ data: APIKey[] }>(`/projects/${projectId}/keys/`);
  return data.data ?? [];
}

export async function createAPIKey(
  projectId: number,
  name: string
): Promise<APIKeyCreated> {
  const { data } = await apiClient.post<{ data: APIKeyCreated }>(
    `/projects/${projectId}/keys/`,
    { name }
  );
  return (data as any).data ?? data;
}

export async function revokeAPIKey(
  projectId: number,
  keyId: number
): Promise<APIKey> {
  const { data } = await apiClient.post<{ data: APIKey }>(
    `/projects/${projectId}/keys/${keyId}/revoke/`
  );
  return (data as any).data ?? data;
}

// ─── Reliability Report ───────────────────────────────────────────────────────

export interface JobReliabilityMetric {
  job_id: number;
  job_name: string;
  task_identifier: string;
  mttr_seconds: number | null;
  mtbf_seconds: number | null;
  total_incidents: number;
  resolved_incidents: number;
}

export interface ReliabilityReport {
  project_id: number;
  start: string;
  end: string;
  total_incidents: number;
  resolved_incidents: number;
  mttr_seconds: number | null;
  mtbf_seconds: number | null;
  per_job: JobReliabilityMetric[];
}

export async function getReliabilityReport(
  projectId: number,
  start: string,
  end: string
): Promise<ReliabilityReport> {
  const { data } = await apiClient.get<any>(
    `/projects/${projectId}/reliability-report/?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
  );
  return (data as any).data ?? data;
}
