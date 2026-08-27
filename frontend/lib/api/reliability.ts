import { apiClient } from "./client";

export type ReliabilityState = "HEALTHY" | "MISSED" | "STALLED" | "OVERDUE" | "ANOMALOUS" | "DISABLED";
export type ExpectationSource = "CONFIGURED" | "BASELINE" | "NONE";
export type ReliabilityConditionType =
  | "MISSED_EXECUTION"
  | "STALLED_EXECUTION"
  | "OVERDUE_EXECUTION"
  | "FAILURE_RATE_ANOMALY"
  | "RETRY_RATE_ANOMALY"
  | "DURATION_ANOMALY"
  | "EXECUTION_VOLUME_ANOMALY";
export type ReliabilityFindingStatus = "ACTIVE" | "RECOVERED";
export type ReliabilityFindingSeverity = "DEGRADED" | "CRITICAL";

export interface JobExpectation {
  id: number | null;
  job: number;
  expected_interval_seconds: number | null;
  max_runtime_seconds: number | null;
  grace_period_seconds: number;
  max_queue_delay_seconds: number | null;
  is_enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface JobBaseline {
  id: number;
  job: number;
  sample_window_days: number;
  total_executions_analyzed: number;
  is_sufficient: boolean;
  avg_interval_seconds: number | null;
  median_interval_seconds: number | null;
  min_interval_seconds: number | null;
  max_interval_seconds: number | null;
  avg_runtime_ms: number | null;
  p50_runtime_ms: number | null;
  p95_runtime_ms: number | null;
  p99_runtime_ms: number | null;
  failure_rate: number | null;
  retry_rate: number | null;
  avg_hourly_volume: number | null;
  metrics_summary: Record<string, unknown>;
  calculated_at: string;
}

export interface ReliabilityFinding {
  id: number;
  job: number;
  job_name?: string;
  project_id?: number;
  project_name?: string;
  execution: number | null;
  incident: number | null;
  condition_type: ReliabilityConditionType;
  status: ReliabilityFindingStatus;
  severity: ReliabilityFindingSeverity;
  details: Record<string, unknown>;
  detected_at: string;
  recovered_at: string | null;
  recovery_reason?: string | null;
  last_evaluated_at: string;
}

export interface LatestReliabilityExecution {
  id: number;
  status: string;
  duration_ms: number | null;
  last_event_at: string;
}

export interface AdaptiveThresholds {
  failure_rate: number | null;
  retry_rate: number | null;
  p95_duration_ms: number | null;
  is_available: boolean;
  source: string;
}

export interface BehaviorMetricComparison {
  current: number | null;
  baseline: number | null;
  adaptive_threshold?: number | null;
  deviation_ratio: number | null;
}

export interface BehaviorComparison {
  observation_window_minutes: number;
  sample_count: number;
  failure_rate: BehaviorMetricComparison;
  retry_rate: BehaviorMetricComparison;
  p95_duration_ms: BehaviorMetricComparison;
  hourly_volume: BehaviorMetricComparison;
}

export interface JobReliabilityOverview {
  job_id: number;
  job_name: string;
  task_identifier: string;
  current_state: ReliabilityState;
  is_enabled: boolean;
  expectation_source: ExpectationSource;
  expected_interval_seconds: number | null;
  max_runtime_seconds: number | null;
  grace_period_seconds: number;
  last_execution_at: string | null;
  next_expected_at: string | null;
  missed_after_at: string | null;
  overdue_by_seconds: number;
  latest_execution: LatestReliabilityExecution | null;
  active_findings: ReliabilityFinding[];
  active_anomalies: ReliabilityFinding[];
  recent_findings: ReliabilityFinding[];
  baseline: JobBaseline | null;
  expectation: JobExpectation | null;
  adaptive_thresholds: AdaptiveThresholds;
  behavior_comparison: BehaviorComparison;
}

export interface ProjectReliabilityJobSummary {
  job_id: number;
  job_name: string;
  task_identifier: string;
  current_state: ReliabilityState;
  expectation_source: ExpectationSource;
  expected_interval_seconds: number | null;
  max_runtime_seconds: number | null;
  last_execution_at: string | null;
  next_expected_at: string | null;
  missed_after_at: string | null;
  overdue_by_seconds: number;
  active_findings_count: number;
}

export interface ProjectReliabilityOverview {
  project_id: number;
  project_name: string;
  total_jobs: number;
  healthy_jobs_count: number;
  missed_jobs_count: number;
  stalled_jobs_count: number;
  overdue_jobs_count: number;
  anomalous_jobs_count: number;
  active_findings_count: number;
  jobs: ProjectReliabilityJobSummary[];
}

export interface RecalculateBaselineResponse {
  status: string;
  message: string;
  job_id: number;
  sample_window_days: number;
}

export interface ReliabilityFindingFilters {
  job?: number;
  condition_type?: ReliabilityConditionType;
  status?: ReliabilityFindingStatus;
  severity?: ReliabilityFindingSeverity;
  page?: number;
}

export interface PaginatedReliabilityFindings {
  data: ReliabilityFinding[];
  page: number;
  totalPages: number;
  totalItems: number;
}

export async function getJobReliability(jobId: number): Promise<JobReliabilityOverview> {
  const res = await apiClient.get<JobReliabilityOverview | { data: JobReliabilityOverview }>(
    `/reliability/jobs/${jobId}/`
  );
  return (res.data && "data" in res.data ? res.data.data : res.data) as JobReliabilityOverview;
}

export async function getJobExpectation(jobId: number): Promise<JobExpectation> {
  const res = await apiClient.get<JobExpectation | { data: JobExpectation }>(
    `/reliability/jobs/${jobId}/expectation/`
  );
  return (res.data && "data" in res.data ? res.data.data : res.data) as JobExpectation;
}

export async function updateJobExpectation(
  jobId: number,
  data: Partial<Omit<JobExpectation, "id" | "job" | "created_at" | "updated_at">>
): Promise<JobExpectation> {
  const res = await apiClient.put<JobExpectation | { data: JobExpectation }>(
    `/reliability/jobs/${jobId}/expectation/`,
    data
  );
  return (res.data && "data" in res.data ? res.data.data : res.data) as JobExpectation;
}

export async function recalculateJobBaseline(
  jobId: number,
  data: { sample_window_days?: number } = {}
): Promise<RecalculateBaselineResponse> {
  const res = await apiClient.post<RecalculateBaselineResponse | { data: RecalculateBaselineResponse }>(
    `/reliability/jobs/${jobId}/recalculate-baseline/`,
    data
  );
  return (res.data && "data" in res.data ? res.data.data : res.data) as RecalculateBaselineResponse;
}

export async function getProjectReliability(projectId: number): Promise<ProjectReliabilityOverview> {
  const res = await apiClient.get<ProjectReliabilityOverview | { data: ProjectReliabilityOverview }>(
    `/reliability/projects/${projectId}/`
  );
  return (res.data && "data" in res.data ? res.data.data : res.data) as ProjectReliabilityOverview;
}

export async function getReliabilityFindings(
  filters: ReliabilityFindingFilters = {}
): Promise<PaginatedReliabilityFindings> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.append(key, value.toString());
    }
  });

  const query = params.toString();
  const url = query ? `/reliability/findings/?${query}` : "/reliability/findings/";
  const res = await apiClient.get<
    | ReliabilityFinding[]
    | { data: ReliabilityFinding[]; page?: number; totalPages?: number; totalItems?: number }
  >(url);

  const payload = res.data;
  if ("data" in payload && Array.isArray(payload.data)) {
    return {
      data: payload.data,
      page: payload.page ?? 1,
      totalPages: payload.totalPages ?? 1,
      totalItems: payload.totalItems ?? payload.data.length,
    };
  }

  const list = Array.isArray(payload) ? payload : [];
  return {
    data: list,
    page: 1,
    totalPages: 1,
    totalItems: list.length,
  };
}
