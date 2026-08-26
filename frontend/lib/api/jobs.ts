import { apiClient } from "./client";
import { Project } from "./projects";
import { User } from "./auth";

export interface Job {
  id: number;
  project: number | Project;
  name: string;
  task_identifier: string;
  description: string;
  status: "active" | "inactive";
  verification_status: "verified" | "unverified";
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedJobs {
  data: Job[];
  page: number;
  totalPages: number;
  totalItems: number;
}

interface JobFilters {
  project?: number;
  status?: string;
  search?: string;
  ordering?: string;
  page?: number;
}

export async function getJobsPaginated(filters: JobFilters = {}): Promise<PaginatedJobs> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.append(key, value.toString());
    }
  });

  const query = params.toString();
  const url = query ? `/jobs/?${query}` : "/jobs/";
  const res = await apiClient.get<any>(url);
  const payload = res.data;
  return {
    data: Array.isArray(payload.data) ? payload.data : Array.isArray(payload) ? payload : [],
    page: payload.page ?? 1,
    totalPages: payload.totalPages ?? 1,
    totalItems: payload.totalItems ?? 0,
  };
}

export async function getJobs(projectId?: number, filters: { search?: string; ordering?: string } = {}): Promise<Job[]> {
  const params = new URLSearchParams({ no_pagination: "true" });
  if (projectId) params.append("project", projectId.toString());
  if (filters.search) params.append("search", filters.search);
  if (filters.ordering) params.append("ordering", filters.ordering);
  
  const { data } = await apiClient.get(`/jobs/?${params.toString()}`);
  return data.data ?? [];
}

export async function getJobAnalytics(jobId: number): Promise<any> {
  const { data } = await apiClient.get(`/jobs/${jobId}/analytics/`);
  return data.data ?? data;
}

export async function getJobTrend(jobId: number, bucketType: string = "hour"): Promise<any> {
  const { data } = await apiClient.get(`/jobs/${jobId}/analytics/trend/?bucket_type=${bucketType}`);
  return data.data ?? data;
}

export async function createJob(payload: { project: number, name: string, task_identifier: string, description?: string }): Promise<Job> {
  const { data } = await apiClient.post(`/jobs/`, payload);
  return data.data ?? data;
}

export async function updateJob(jobId: number, payload: { name?: string, description?: string, status?: string }): Promise<Job> {
  const { data } = await apiClient.patch(`/jobs/${jobId}/`, payload);
  return data.data ?? data;
}

export async function deleteJob(jobId: number): Promise<void> {
  await apiClient.delete(`/jobs/${jobId}/`);
}
