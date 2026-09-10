import { AlertMetricType, AlertRule } from "./api/alerts";

export function formatDurationSeconds(seconds?: unknown): string {
  if (seconds === undefined || seconds === null || isNaN(Number(seconds))) return "–";
  const s = Math.round(Number(seconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) {
    return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
  }
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return remM > 0 ? `${h}h ${remM}m` : `${h}h`;
}

export function formatDurationMs(ms?: unknown): string {
  if (ms === undefined || ms === null || isNaN(Number(ms))) return "–";
  const num = Number(ms);
  if (num >= 1000) {
    const s = num / 1000;
    return s >= 60 ? `${(s / 60).toFixed(1)}m (${Math.round(num)}ms)` : `${s.toFixed(2)}s`;
  }
  return `${Math.round(num)}ms`;
}

export type MetricCategory =
  | "Cadence SLA"
  | "Runtime SLA"
  | "Queue Delay SLA"
  | "Intelligent Anomaly"
  | "Standard Metric";

export function getMetricCategory(metricType?: string): MetricCategory {
  switch (metricType) {
    case "MISSED_EXECUTION":
      return "Cadence SLA";
    case "STALLED_EXECUTION":
      return "Runtime SLA";
    case "OVERDUE_EXECUTION":
      return "Queue Delay SLA";
    case "FAILURE_RATE_ANOMALY":
    case "RETRY_RATE_ANOMALY":
    case "DURATION_ANOMALY":
    case "EXECUTION_VOLUME_ANOMALY":
      return "Intelligent Anomaly";
    default:
      return "Standard Metric";
  }
}

export function getMetricLabel(metricType?: string): string {
  switch (metricType) {
    case "MISSED_EXECUTION":
      return "Missed Execution";
    case "STALLED_EXECUTION":
      return "Stalled Execution";
    case "OVERDUE_EXECUTION":
      return "Overdue in Queue";
    case "FAILURE_RATE_ANOMALY":
      return "Failure Rate Anomaly";
    case "RETRY_RATE_ANOMALY":
      return "Retry Rate Anomaly";
    case "DURATION_ANOMALY":
      return "Duration Anomaly";
    case "EXECUTION_VOLUME_ANOMALY":
      return "Execution Volume Anomaly";
    case "FAILURE_RATE":
      return "Failure Rate";
    case "RETRY_RATE":
      return "Retry Rate";
    case "P95_DURATION":
      return "P95 Duration";
    default:
      return metricType ? metricType.replace(/_/g, " ") : "Unknown Metric";
  }
}

export interface TriggerSummary {
  metricType: string;
  category: MetricCategory;
  title: string;
  badgeClass: string;
  primaryValue: string;
  secondaryValue?: string;
  detail: string;
}

export function getTriggerSummary(
  tm: Record<string, unknown> = {},
  rule?: AlertRule | null
): TriggerSummary {
  const rawMetric = tm.metric_type || tm.condition_type || rule?.metric || "UNKNOWN";
  const metricType = String(rawMetric) as AlertMetricType;
  const category = getMetricCategory(metricType);
  const title = getMetricLabel(metricType);

  switch (metricType) {
    case "MISSED_EXECUTION": {
      const overdue = tm.overdue_by_seconds ?? tm.metric_value ?? tm.actual_value;
      const bufferNum = tm.threshold !== undefined ? Number(tm.threshold) : (rule?.threshold ?? 0);
      const overdueStr = formatDurationSeconds(overdue);
      const bufferStr = bufferNum > 0 ? `+${bufferNum}s buffer` : "0s buffer";

      return {
        metricType,
        category,
        title,
        badgeClass: "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20",
        primaryValue: `${overdueStr} overdue`,
        secondaryValue: bufferStr,
        detail: `Overdue by ${overdueStr} (${bufferStr})`,
      };
    }

    case "STALLED_EXECUTION": {
      const runtime = tm.runtime_seconds ?? tm.metric_value;
      const maxRuntime = tm.max_runtime_seconds;
      const runtimeStr = formatDurationSeconds(runtime);
      const limitStr = maxRuntime !== undefined ? formatDurationSeconds(maxRuntime) : undefined;

      return {
        metricType,
        category,
        title,
        badgeClass: "bg-destructive/10 text-destructive border-destructive/20",
        primaryValue: `Running for ${runtimeStr}`,
        secondaryValue: limitStr ? `Limit: ${limitStr}` : undefined,
        detail: `Running for ${runtimeStr}${limitStr ? ` (Limit: ${limitStr})` : ""}`,
      };
    }

    case "OVERDUE_EXECUTION": {
      const queued = tm.queued_seconds ?? tm.metric_value;
      const maxQueue = tm.max_queue_delay_seconds;
      const queuedStr = formatDurationSeconds(queued);
      const limitStr = maxQueue !== undefined ? formatDurationSeconds(maxQueue) : undefined;

      return {
        metricType,
        category,
        title,
        badgeClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
        primaryValue: `Queued for ${queuedStr}`,
        secondaryValue: limitStr ? `Limit: ${limitStr}` : undefined,
        detail: `Queued for ${queuedStr}${limitStr ? ` (Limit: ${limitStr})` : ""}`,
      };
    }

    case "FAILURE_RATE_ANOMALY":
    case "RETRY_RATE_ANOMALY": {
      const current = tm.current_value ?? tm.metric_value;
      const base = tm.baseline_value;
      const ratio = tm.deviation_ratio;
      const currentStr = current !== undefined ? `${Number(current).toFixed(1)}%` : "–";
      const baseStr = base !== undefined ? `${Number(base).toFixed(1)}%` : "–";
      const ratioStr = ratio !== undefined ? `${ratio}× baseline` : undefined;

      return {
        metricType,
        category,
        title,
        badgeClass: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20",
        primaryValue: `Observed: ${currentStr}`,
        secondaryValue: `Base: ${baseStr}${ratioStr ? ` (${ratioStr})` : ""}`,
        detail: `Observed: ${currentStr} (Baseline: ${baseStr}${ratioStr ? `, ${ratioStr}` : ""})`,
      };
    }

    case "DURATION_ANOMALY": {
      const current = tm.current_value ?? tm.metric_value;
      const base = tm.baseline_value;
      const ratio = tm.deviation_ratio;
      const currentStr = formatDurationMs(current);
      const baseStr = formatDurationMs(base);
      const ratioStr = ratio !== undefined ? `${ratio}× baseline` : undefined;

      return {
        metricType,
        category,
        title,
        badgeClass: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20",
        primaryValue: `Observed: ${currentStr}`,
        secondaryValue: `Base: ${baseStr}${ratioStr ? ` (${ratioStr})` : ""}`,
        detail: `Observed: ${currentStr} (Baseline: ${baseStr}${ratioStr ? `, ${ratioStr}` : ""})`,
      };
    }

    case "EXECUTION_VOLUME_ANOMALY": {
      const current = tm.current_value ?? tm.metric_value;
      const base = tm.baseline_value;
      const ratio = tm.deviation_ratio;
      const currentStr = current !== undefined ? `${current} runs` : "–";
      const baseStr = base !== undefined ? `${base}/hr` : "–";
      const ratioStr = ratio !== undefined ? `${ratio}×` : undefined;

      return {
        metricType,
        category,
        title,
        badgeClass: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20",
        primaryValue: `Volume: ${currentStr}`,
        secondaryValue: `Avg: ${baseStr}${ratioStr ? ` (${ratioStr})` : ""}`,
        detail: `Volume: ${currentStr} (Avg: ${baseStr}${ratioStr ? `, ${ratioStr}` : ""})`,
      };
    }

    case "FAILURE_RATE":
    case "RETRY_RATE": {
      const val = tm.metric_value ?? tm.actual_value;
      const th = tm.threshold !== undefined ? tm.threshold : rule?.threshold;
      const valStr = val !== undefined ? `${Number(val).toFixed(1)}%` : "–";
      const thStr = th !== undefined ? `${Number(th).toFixed(1)}%` : "–";

      return {
        metricType,
        category,
        title,
        badgeClass: "bg-destructive/10 text-destructive border-destructive/20",
        primaryValue: `Actual: ${valStr}`,
        secondaryValue: `Threshold: ${thStr}`,
        detail: `Actual: ${valStr} (Threshold: ${thStr})`,
      };
    }

    case "P95_DURATION": {
      const val = tm.metric_value ?? tm.actual_value;
      const th = tm.threshold !== undefined ? tm.threshold : rule?.threshold;
      const valStr = formatDurationMs(val);
      const thStr = formatDurationMs(th);

      return {
        metricType,
        category,
        title,
        badgeClass: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
        primaryValue: `Actual: ${valStr}`,
        secondaryValue: `Threshold: ${thStr}`,
        detail: `Actual: ${valStr} (Threshold: ${thStr})`,
      };
    }

    default: {
      const val = tm.metric_value ?? tm.actual_value;
      const th = tm.threshold !== undefined ? tm.threshold : rule?.threshold;
      const valStr = val !== undefined ? String(val) : "–";
      const thStr = th !== undefined ? String(th) : "–";

      return {
        metricType,
        category,
        title,
        badgeClass: "bg-muted text-muted-foreground border-border",
        primaryValue: `Actual: ${valStr}`,
        secondaryValue: `Threshold: ${thStr}`,
        detail: `Actual: ${valStr} (Threshold: ${thStr})`,
      };
    }
  }
}
