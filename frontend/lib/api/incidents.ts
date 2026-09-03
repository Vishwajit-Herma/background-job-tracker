import { apiClient } from "./client";

// ─── Core Incident Types ──────────────────────────────────────────────────────

export interface IncidentEvent {
  id: number;
  event_type:
    | "CREATED"
    | "ASSIGNED"
    | "ACKNOWLEDGED"
    | "NOTE_ADDED"
    | "REOPENED"
    | "AUTO_RESOLVED"
    | "MANUALLY_RESOLVED"
    | "RUNBOOK_STARTED"
    | "RUNBOOK_COMPLETED"
    | "RUNBOOK_CANCELLED"
    | "POSTMORTEM_SUBMITTED"
    | "POSTMORTEM_COMPLETED";
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

// ─── Intelligence Types ───────────────────────────────────────────────────────

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

// ─── Runbook Types ──────────────────────────────────────────────────

export interface RunbookStep {
  id: string;
  title: string;
  description?: string;
  order?: number;
}

export type RunbookTriggerType =
  | "MISSED_EXECUTION"
  | "STALLED_EXECUTION"
  | "OVERDUE_EXECUTION"
  | "FAILURE_RATE"
  | "FAILURE_RATE_ANOMALY"
  | "RETRY_RATE"
  | "RETRY_RATE_ANOMALY"
  | "DURATION_ANOMALY"
  | "EXECUTION_VOLUME_ANOMALY";

export interface Runbook {
  id: number;
  project: number;
  job: number | null;
  name: string;
  description: string;
  trigger_type: string | null;
  is_active: boolean;
  steps: RunbookStep[];
  priority?: number;
  match_priority?: number;
  match_reason?: string;
  created_by?: number | null;
  created_by_name?: string | null;
  updated_by?: number | null;
  updated_by_name?: string | null;
  created_at: string;
  updated_at: string;
}

export type RunbookExecutionStatus = "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
export type StepState = "PENDING" | "IN_PROGRESS" | "COMPLETED" | "SKIPPED";

export interface RunbookExecution {
  id: number;
  incident: number;
  runbook: number;
  runbook_name?: string;
  runbook_details?: Runbook;
  started_by?: number | null;
  started_by_name?: string | null;
  status: RunbookExecutionStatus;
  started_at: string | null;
  completed_at: string | null;
  step_states: Record<string, StepState>;
  step_history: Array<{
    step_id: string;
    from?: StepState;
    to?: StepState;
    from_state?: StepState;
    to_state?: StepState;
    actor_id?: number | null;
    actor_name?: string | null;
    timestamp: string;
  }>;
}

// ─── Postmortem Types ───────────────────────────────────────────────

export type PostmortemStatus = "PENDING" | "IN_REVIEW" | "COMPLETED";
export type ActionItemStatus = "PENDING" | "IN_PROGRESS" | "COMPLETED";

export interface PostmortemActionItem {
  id: number;
  postmortem: number;
  title: string;
  description: string;
  status: ActionItemStatus;
  owner: number | null;
  owner_name: string | null;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Postmortem {
  id: number;
  incident: number;
  status: PostmortemStatus;
  summary: string;
  impact_summary: string;
  probable_cause: string;
  confirmed_root_cause: string;
  resolution: string;
  contributing_factors: string;
  timeline: string;
  what_went_well: string;
  what_went_wrong: string;
  reviewed_by: number | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  action_items: PostmortemActionItem[];
  created_by: number | null;
  created_by_name: string | null;
  updated_by: number | null;
  updated_by_name: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Knowledge Type ─────────────────────────────────────────────────

export interface IncidentKnowledge {
  incident: Incident;
  events: IncidentEvent[];
  intelligence: IncidentIntelligence | null;
  runbook_executions: RunbookExecution[];
  postmortem: Postmortem | null;
}

// ─── Core Incident API ────────────────────────────────────────────────────────

export async function getIncidents(
  filters: {
    page?: number;
    search?: string;
    ordering?: string;
    status?: string;
    severity?: string;
    assigned_to__user?: number | string;
  } = {}
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

export async function assignIncident(id: number, memberId: number | null): Promise<Incident> {
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

export async function getIncidentIntelligence(id: number): Promise<IncidentIntelligence> {
  const res = await apiClient.get<any>(`/incidents/${id}/intelligence/`);
  return res.data?.data ?? res.data;
}

// ─── Runbook API ────────────────────────────────────────────────────

export async function getRecommendedRunbooks(incidentId: number): Promise<Runbook[]> {
  const res = await apiClient.get<any>(`/incidents/${incidentId}/recommended-runbooks/`);
  const data = res.data?.data ?? res.data;
  return Array.isArray(data) ? data : [];
}

export async function executeRunbook(incidentId: number, runbookId: number): Promise<RunbookExecution> {
  const res = await apiClient.post<any>(`/incidents/${incidentId}/execute-runbook/`, {
    runbook_id: runbookId,
  });
  return res.data?.data ?? res.data;
}

export async function getRunbookExecutions(incidentId: number): Promise<RunbookExecution[]> {
  const res = await apiClient.get<any>(`/incidents/${incidentId}/runbook-executions/`);
  const data = res.data?.data ?? res.data;
  return Array.isArray(data) ? data : [];
}

export async function updateRunbookExecutionStatus(
  incidentId: number,
  executionId: number,
  newStatus: RunbookExecutionStatus
): Promise<RunbookExecution> {
  const res = await apiClient.post<any>(
    `/incidents/${incidentId}/runbook-execution/${executionId}/status/`,
    { status: newStatus }
  );
  return res.data?.data ?? res.data;
}

export async function transitionRunbookStep(
  incidentId: number,
  payload: {
    execution_id: number;
    step_id: string;
    from_state: StepState;
    to_state: StepState;
  }
): Promise<RunbookExecution> {
  const res = await apiClient.post<any>(`/incidents/${incidentId}/transition-step/`, payload);
  return res.data?.data ?? res.data;
}

export async function getRunbooks(
  params: {
    project?: number;
    job?: number;
    is_active?: boolean;
    trigger_type?: string;
    search?: string;
    ordering?: string;
  } = {}
): Promise<Runbook[]> {
  const query = new URLSearchParams();
  if (params.project) query.append("project", params.project.toString());
  if (params.job) query.append("job", params.job.toString());
  if (params.is_active !== undefined) query.append("is_active", params.is_active.toString());
  if (params.trigger_type) query.append("trigger_type", params.trigger_type);
  if (params.search) query.append("search", params.search);
  if (params.ordering) query.append("ordering", params.ordering);

  const res = await apiClient.get<any>(`/incidents/runbooks/?${query.toString()}`);
  const data = res.data?.data ?? res.data;
  return Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : [];
}

export async function getRunbook(id: number): Promise<Runbook> {
  const res = await apiClient.get<any>(`/incidents/runbooks/${id}/`);
  return res.data?.data ?? res.data;
}

export async function createRunbook(payload: {
  project: number;
  job?: number | null;
  name: string;
  description?: string;
  trigger_type?: string | null;
  steps: RunbookStep[];
  is_active?: boolean;
}): Promise<Runbook> {
  const res = await apiClient.post<any>(`/incidents/runbooks/`, payload);
  return res.data?.data ?? res.data;
}

export async function updateRunbook(
  id: number,
  payload: Partial<{
    project: number;
    job: number | null;
    name: string;
    description: string;
    trigger_type: string | null;
    steps: RunbookStep[];
    is_active: boolean;
  }>
): Promise<Runbook> {
  const res = await apiClient.patch<any>(`/incidents/runbooks/${id}/`, payload);
  return res.data?.data ?? res.data;
}

export async function deleteRunbook(id: number): Promise<void> {
  await apiClient.delete(`/incidents/runbooks/${id}/`);
}

export async function deactivateRunbook(id: number): Promise<Runbook> {
  const res = await apiClient.post<any>(`/incidents/runbooks/${id}/deactivate/`);
  return res.data?.data ?? res.data;
}

// ─── Postmortem API ─────────────────────────────────────────────────

export async function getPostmortem(incidentId: number): Promise<Postmortem> {
  const res = await apiClient.get<any>(`/incidents/${incidentId}/postmortem/`);
  return res.data?.data ?? res.data;
}

export async function savePostmortem(
  incidentId: number,
  data: Partial<
    Omit<
      Postmortem,
      | "id"
      | "incident"
      | "action_items"
      | "reviewed_by"
      | "reviewed_by_name"
      | "reviewed_at"
      | "created_by"
      | "created_by_name"
      | "updated_by"
      | "updated_by_name"
      | "created_at"
      | "updated_at"
    >
  >
): Promise<Postmortem> {
  const res = await apiClient.post<any>(`/incidents/${incidentId}/postmortem/`, data);
  return res.data?.data ?? res.data;
}

export async function submitPostmortemReview(incidentId: number): Promise<Postmortem> {
  const res = await apiClient.post<any>(`/incidents/${incidentId}/postmortem/submit-review/`);
  return res.data?.data ?? res.data;
}

export async function completePostmortemReview(incidentId: number): Promise<Postmortem> {
  const res = await apiClient.post<any>(`/incidents/${incidentId}/postmortem/complete/`);
  return res.data?.data ?? res.data;
}

export async function getActionItems(incidentId: number): Promise<PostmortemActionItem[]> {
  const res = await apiClient.get<any>(`/incidents/${incidentId}/postmortem/action-items/`);
  const data = res.data?.data ?? res.data;
  return Array.isArray(data) ? data : [];
}

export async function createActionItem(
  incidentId: number,
  data: {
    title: string;
    description?: string;
    owner?: number | null;
    status?: ActionItemStatus;
    due_date?: string | null;
  }
): Promise<PostmortemActionItem> {
  const res = await apiClient.post<any>(`/incidents/${incidentId}/postmortem/action-items/`, data);
  return res.data?.data ?? res.data;
}

export async function updateActionItem(
  incidentId: number,
  itemId: number,
  data: Partial<{
    title: string;
    description: string;
    owner: number | null;
    status: ActionItemStatus;
    due_date: string | null;
  }>
): Promise<PostmortemActionItem> {
  const res = await apiClient.patch<any>(
    `/incidents/${incidentId}/postmortem/action-items/${itemId}/`,
    data
  );
  return res.data?.data ?? res.data;
}

export async function deleteActionItem(incidentId: number, itemId: number): Promise<void> {
  await apiClient.delete(`/incidents/${incidentId}/postmortem/action-items/${itemId}/`);
}

// ─── Knowledge API ──────────────────────────────────────────────────

export async function getIncidentKnowledge(incidentId: number): Promise<IncidentKnowledge> {
  const res = await apiClient.get<any>(`/incidents/${incidentId}/knowledge/`);
  return res.data?.data ?? res.data;
}
