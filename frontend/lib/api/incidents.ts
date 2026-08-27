import { apiClient } from "./client";

export interface IncidentEvent {
  id: number;
  event_type: "CREATED" | "ASSIGNED" | "ACKNOWLEDGED" | "NOTE_ADDED" | "REOPENED" | "AUTO_RESOLVED" | "MANUALLY_RESOLVED";
  actor: number | null;
  actor_name: string | null;
  event_time: string;
  metadata: Record<string, any>;
}

export interface IncidentNote {
  id: number;
  incident: number;
  author: number;
  author_name: string;
  content: string;
  created_at: string;
}

export interface Incident {
  id: number;
  project: number;
  job: number | null;
  alert_rule: number | null;
  status: "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
  severity: "DEGRADED" | "CRITICAL";
  assigned_to: number | null;
  assigned_to_user_id: number | null;
  assigned_to_name: string | null;
  assigned_at: string | null;
  assigned_by: number | null;
  acknowledged_at: string | null;
  acknowledged_by: number | null;
  resolved_at: string | null;
  resolution_type: "MANUAL" | "AUTOMATIC" | null;
  resolved_by: number | null;
  trigger_metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface PaginatedIncidents {
  data: Incident[];
  page: number;
  totalPages: number;
  totalItems: number;
}

interface IncidentFilters {
  project?: number;
  job?: number;
  status?: string;
  severity?: string;
  assigned_to?: number;
  alert_rule?: number;
  page?: number;
  search?: string;
  ordering?: string;
}

export async function getIncidents(
  filters: { page?: number; search?: string; ordering?: string; status?: string; severity?: string; assigned_to__user?: number | string } = {}
): Promise<PaginatedIncidents> {
  const params = new URLSearchParams();
  if (filters.page) params.append("page", filters.page.toString());
  if (filters.search) params.append("search", filters.search);
  if (filters.ordering) params.append("ordering", filters.ordering);
  if (filters.status && filters.status !== "all") params.append("status", filters.status);
  if (filters.severity && filters.severity !== "all") params.append("severity", filters.severity);
  if (filters.assigned_to__user) params.append("assigned_to__user", filters.assigned_to__user.toString());

  const res = await apiClient.get<any>(`/incidents/?${params.toString()}`);
  const payload = res.data;
  return {
    data: Array.isArray(payload.data) ? payload.data : Array.isArray(payload) ? payload : [],
    page: payload.page ?? 1,
    totalPages: payload.totalPages ?? 1,
    totalItems: payload.totalItems ?? 0,
  };
}

export async function getIncident(id: number): Promise<Incident> {
  const res = await apiClient.get<any>(`/incidents/${id}/`);
  return res.data?.data ?? res.data;
}

export async function assignIncident(id: number, memberId: number): Promise<Incident> {
  const res = await apiClient.post<any>(`/incidents/${id}/assign/`, { member_id: memberId });
  return res.data?.data ?? res.data;
}

export async function acknowledgeIncident(id: number): Promise<Incident> {
  const res = await apiClient.post<any>(`/incidents/${id}/acknowledge/`);
  return res.data?.data ?? res.data;
}

export async function resolveIncident(id: number): Promise<Incident> {
  const res = await apiClient.post<any>(`/incidents/${id}/resolve/`);
  return res.data?.data ?? res.data;
}

export async function reopenIncident(id: number): Promise<Incident> {
  const res = await apiClient.post<any>(`/incidents/${id}/reopen/`);
  return res.data?.data ?? res.data;
}

export async function getIncidentEvents(id: number): Promise<IncidentEvent[]> {
  const res = await apiClient.get<any>(`/incidents/${id}/events/`);
  const data = res.data?.data ?? res.data;
  return Array.isArray(data) ? data : [];
}

export async function getIncidentNotes(id: number): Promise<IncidentNote[]> {
  const res = await apiClient.get<any>(`/incidents/${id}/notes/`);
  const data = res.data?.data ?? res.data;
  return Array.isArray(data) ? data : [];
}

export async function addIncidentNote(id: number, content: string): Promise<IncidentNote> {
  const res = await apiClient.post<any>(`/incidents/${id}/notes/`, { content });
  return res.data?.data ?? res.data;
}

export type ConfidenceLevel = "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT_EVIDENCE";
export type CandidateType = "WORKER" | "QUEUE" | "JOB" | "ANOMALY" | "INSUFFICIENT_EVIDENCE";

export interface ProbableCauseCandidate {
  candidate: CandidateType;
  value: string;
  confidence: ConfidenceLevel;
  evidence: string[];
}

export interface IncidentImpact {
  window_start: string;
  window_end: string;
  window_minutes: number;
  incident_duration_seconds?: number;
  affected_jobs_count: number;
  affected_jobs: Array<{
    id: number;
    name: string;
    task_identifier: string;
    total: number;
    failures: number;
    retries: number;
  }>;
  affected_executions_count: number;
  failures_count: number;
  retries_count: number;
  successes_count: number;
  failure_rate: number;
  retry_rate: number;
  affected_workers_count: number;
  affected_workers: string[];
  affected_queues_count: number;
  affected_queues: string[];
  baseline_comparisons: {
    baseline_failure_rate?: number;
    current_failure_rate?: number;
    failure_rate_multiplier?: number | null;
    baseline_retry_rate?: number;
    current_retry_rate?: number;
    retry_rate_multiplier?: number | null;
    baseline_p95_ms?: number | null;
  };
}

export interface IncidentCorrelation {
  target_type: "FINDING" | "WORKER" | "QUEUE" | "INCIDENT";
  target_id: number | null;
  target_name: string;
  reasons: string[];
  correlation_strength: "STRONG" | "MODERATE" | "WEAK";
}

export interface IncidentIntelligence {
  id?: number;
  incident?: number;
  status: "READY" | "PENDING";
  message?: string;
  impact: IncidentImpact | null;
  correlations: IncidentCorrelation[];
  probable_causes: ProbableCauseCandidate[];
  analysis_window_start: string | null;
  analysis_window_end: string | null;
  analysis_version: string;
  calculated_at: string | null;
}

export async function getIncidentIntelligence(id: number): Promise<IncidentIntelligence> {
  const res = await apiClient.get<any>(`/incidents/${id}/intelligence/`);
  return res.data?.data ?? res.data;
}

