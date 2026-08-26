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
  created_by: number | null;
  modified_by: number | null;
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
