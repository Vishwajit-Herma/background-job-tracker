import { apiClient } from "./client";

export interface Period {
  start: string;
  end: string;
}

export interface FailingJob {
  job_id: number;
  name: string;
  task_identifier: string;
  execution_count: number;
  failure_count: number;
  failure_rate: number;
}

export interface SlowJob {
  job_id: number;
  name: string;
  task_identifier: string;
  average_duration_ms: number;
  p95_duration_ms: number | null;
}

export interface AnalyticsQueueSummary {
  queue: string;
  count: number;
  failures: number;
  retries: number;
  successes: number;
  success_rate: number;
  failure_rate: number;
  retry_rate: number;
}

export interface AnalyticsWorkerSummary {
  worker: string;
  count: number;
  failures: number;
  retries: number;
  successes: number;
  success_rate: number;
  failure_rate: number;
  retry_rate: number;
}

export interface AnalyticsError {
  error_type: string;
  count: number;
  affected_jobs?: number;
}

export interface AnalyticsMetricDelta {
  current: number | null;
  previous: number | null;
  delta_points: number | null;
  delta_percent: number | null;
  comparison_period: string | null;
}

export interface AnalyticsThresholds {
  failure_rate?: number;
  retry_rate?: number;
  p95_duration?: number;
}

export interface ProjectAnalytics {
  project_id: number;
  period: Period;
  executions: AnalyticsMetricDelta;
  successes: number;
  failures: number;
  retries: number;
  success_rate: AnalyticsMetricDelta;
  failure_rate: AnalyticsMetricDelta;
  retry_rate: AnalyticsMetricDelta;
  average_duration_ms: AnalyticsMetricDelta;
  p50_duration_ms: number | null;
  p95_duration_ms: AnalyticsMetricDelta;
  p99_duration_ms: number | null;
  healthy_jobs: number;
  degraded_jobs: number;
  critical_jobs: number;
  health: "HEALTHY" | "DEGRADED" | "CRITICAL";
  open_incidents: number;
  critical_incidents: number;
  top_failing_jobs: FailingJob[];
  slowest_jobs: SlowJob[];
  queue_summary: AnalyticsQueueSummary[];
  worker_summary: AnalyticsWorkerSummary[];
  errors: AnalyticsError[];
  thresholds?: AnalyticsThresholds;
}

export interface JobAnalytics {
  job_id: number;
  job_name: string;
  task_identifier: string;
  period: Period;
  executions: AnalyticsMetricDelta;
  successes: number;
  failures: number;
  retries: number;
  success_rate: AnalyticsMetricDelta;
  failure_rate: AnalyticsMetricDelta;
  retry_rate: AnalyticsMetricDelta;
  average_duration_ms: AnalyticsMetricDelta;
  p50_duration_ms: number | null;
  p95_duration_ms: AnalyticsMetricDelta;
  p99_duration_ms: number | null;
  health: "HEALTHY" | "DEGRADED" | "CRITICAL";
  open_incidents: number;
  critical_incidents: number;
  queue_summary: AnalyticsQueueSummary[];
  worker_summary: AnalyticsWorkerSummary[];
  errors: AnalyticsError[];
  thresholds?: AnalyticsThresholds;
}

export interface TrendPoint {
  timestamp: string;
  executions: number;
  successes: number;
  failures: number;
  retries: number;
  success_rate: number;
  average_duration_ms: number | null;
  p95_duration_ms: number | null;
}

export interface TrendResponse {
  trend: TrendPoint[];
}

export interface AnalyticsFilters {
  start?: string;
  end?: string;
  range?: "last_1_hour" | "last_24_hours" | "last_7_days" | "last_30_days" | string;
  jobs?: string;
  queue?: string;
  worker?: string;
}

function buildAnalyticsParams(filters: AnalyticsFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.start) params.append("start", filters.start);
  if (filters.end) params.append("end", filters.end);
  if (filters.range) params.append("range", filters.range);
  if (filters.jobs) params.append("jobs", filters.jobs);
  if (filters.queue) params.append("queue", filters.queue);
  if (filters.worker) params.append("worker", filters.worker);
  return params;
}

export async function getProjectAnalytics(projectId: number, filters: AnalyticsFilters = {}): Promise<ProjectAnalytics> {
  const params = buildAnalyticsParams(filters);
  const query = params.toString();
  const url = `/projects/${projectId}/analytics/${query ? "?" + query : ""}`;
  const { data } = await apiClient.get(url);
  return (data as any)?.data ?? data;
}

export async function getProjectAnalyticsTrend(projectId: number, filters: AnalyticsFilters = {}): Promise<TrendResponse> {
  const params = buildAnalyticsParams(filters);
  const query = params.toString();
  const url = `/projects/${projectId}/analytics/trend/${query ? "?" + query : ""}`;
  const { data } = await apiClient.get(url);
  const unwrapped = (data as any)?.data ?? data;
  return Array.isArray(unwrapped) ? { trend: unwrapped } : unwrapped;
}

export async function getJobAnalytics(jobId: number, filters: AnalyticsFilters = {}): Promise<JobAnalytics> {
  const params = buildAnalyticsParams(filters);
  const query = params.toString();
  const url = `/jobs/${jobId}/analytics/${query ? "?" + query : ""}`;
  const { data } = await apiClient.get(url);
  return (data as any)?.data ?? data;
}

export async function getJobAnalyticsTrend(jobId: number, filters: AnalyticsFilters = {}): Promise<TrendResponse> {
  const params = buildAnalyticsParams(filters);
  const query = params.toString();
  const url = `/jobs/${jobId}/analytics/trend/${query ? "?" + query : ""}`;
  const { data } = await apiClient.get(url);
  const unwrapped = (data as any)?.data ?? data;
  return Array.isArray(unwrapped) ? { trend: unwrapped } : unwrapped;
}
