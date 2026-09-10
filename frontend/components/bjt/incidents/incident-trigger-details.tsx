"use client";

import Link from "next/link";
import { AlertRule } from "@/lib/api/alerts";
import { Badge } from "@/components/ui/badge";
import {
  formatDurationSeconds,
  formatDurationMs,
  getMetricCategory,
  getMetricLabel,
} from "@/lib/incident-trigger-utils";
import {
  Activity,
  AlertTriangle,
  Clock,
  ExternalLink,
  Flame,
  History,
  Hourglass,
  Layers,
  Sparkles,
} from "lucide-react";

interface IncidentTriggerDetailsProps {
  triggerMetadata: Record<string, unknown>;
  alertRule?: AlertRule | null;
  ruleId?: number | null;
  jobId?: number | null;
}

export function IncidentTriggerDetails({
  triggerMetadata = {},
  alertRule,
  ruleId,
  jobId,
}: IncidentTriggerDetailsProps) {
  const tm = triggerMetadata as Record<string, any>;
  const metricType = ((tm.metric_type || tm.condition_type || alertRule?.metric || "UNKNOWN") as string);
  const category = getMetricCategory(metricType);
  const metricTitle = getMetricLabel(metricType);

  const getCategoryIcon = () => {
    switch (category) {
      case "Cadence SLA":
        return <Clock className="h-4 w-4 text-orange-500" />;
      case "Runtime SLA":
        return <Flame className="h-4 w-4 text-destructive" />;
      case "Queue Delay SLA":
        return <Hourglass className="h-4 w-4 text-amber-500" />;
      case "Intelligent Anomaly":
        return <Sparkles className="h-4 w-4 text-purple-600 dark:text-purple-400" />;
      default:
        return <Activity className="h-4 w-4 text-primary" />;
    }
  };

  const getCategoryBadgeStyle = () => {
    switch (category) {
      case "Cadence SLA":
        return "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20";
      case "Runtime SLA":
        return "bg-destructive/10 text-destructive border-destructive/20";
      case "Queue Delay SLA":
        return "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20";
      case "Intelligent Anomaly":
        return "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20";
      default:
        return "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20";
    }
  };

  const formatDateTime = (isoString?: string | null) => {
    if (!isoString) return "–";
    try {
      const d = new Date(isoString);
      return isNaN(d.getTime()) ? isoString : d.toLocaleString();
    } catch {
      return isoString;
    }
  };

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-3.5">
        <div className="flex items-center gap-2">
          {getCategoryIcon()}
          <h3 className="font-semibold text-foreground text-base">Trigger Details</h3>
        </div>
        <Badge variant="outline" className={`text-xs px-2.5 py-0.5 font-medium ${getCategoryBadgeStyle()}`}>
          {category}
        </Badge>
      </div>

      {/* Metric Title & Explanation */}
      <div>
        <p className="text-[11px] text-muted-foreground uppercase tracking-wider font-semibold">
          Evaluated Condition
        </p>
        <p className="text-base font-bold text-foreground mt-0.5 flex items-center gap-2">
          {metricTitle}
        </p>
      </div>

      {/* ── Dynamic Rule-Type Specific Stat Cards ── */}
      {metricType === "MISSED_EXECUTION" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3.5">
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3">
              <p className="text-xs text-muted-foreground font-medium">Overdue By</p>
              <p className="text-2xl font-bold text-destructive mt-1 font-mono">
                {formatDurationSeconds(tm.overdue_by_seconds ?? tm.metric_value ?? tm.actual_value)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">Elapsed past scheduled deadline</p>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground font-medium">Extra Grace Buffer</p>
              <p className="text-2xl font-bold text-foreground mt-1 font-mono">
                {Number(tm.threshold ?? alertRule?.threshold ?? 0) > 0
                  ? `+${tm.threshold ?? alertRule?.threshold}s`
                  : "0s (None)"}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">Rule tolerance buffer</p>
            </div>
          </div>

          {/* Detailed Cadence Context */}
          <div className="rounded-lg border bg-muted/20 p-3.5 space-y-2 text-xs">
            <p className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
              <Clock className="h-3.5 w-3.5 text-orange-500" /> Cadence Schedule Breakdown
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 border-t border-border/50 text-[11px]">
              {tm.expected_interval_seconds !== undefined && (
                <div>
                  <span className="text-muted-foreground">Expected Cadence: </span>
                  <strong className="text-foreground font-medium">
                    Every {formatDurationSeconds(tm.expected_interval_seconds)}
                  </strong>
                </div>
              )}
              {tm.grace_period_seconds !== undefined && (
                <div>
                  <span className="text-muted-foreground">Base Job Grace: </span>
                  <strong className="text-foreground font-medium">{tm.grace_period_seconds}s</strong>
                </div>
              )}
              {tm.last_occurrence_at && (
                <div className="col-span-1 sm:col-span-2">
                  <span className="text-muted-foreground">Last Observed Run: </span>
                  <span className="text-foreground font-medium">{formatDateTime(tm.last_occurrence_at)}</span>
                </div>
              )}
              {tm.threshold_at && (
                <div className="col-span-1 sm:col-span-2">
                  <span className="text-muted-foreground">Expected Deadline: </span>
                  <span className="text-foreground font-medium">{formatDateTime(tm.threshold_at)}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {metricType === "STALLED_EXECUTION" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3.5">
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3">
              <p className="text-xs text-muted-foreground font-medium">Current Runtime</p>
              <p className="text-2xl font-bold text-destructive mt-1 font-mono">
                {formatDurationSeconds(tm.runtime_seconds ?? tm.metric_value)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {tm.exceeded_by_seconds !== undefined
                  ? `Exceeded limit by ${formatDurationSeconds(tm.exceeded_by_seconds)}`
                  : "Currently executing"}
              </p>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground font-medium">Max Allowed Runtime</p>
              <p className="text-2xl font-bold text-foreground mt-1 font-mono">
                {formatDurationSeconds(tm.max_runtime_seconds)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Buffer: +{Number(tm.threshold ?? alertRule?.threshold ?? 0)}s
              </p>
            </div>
          </div>

          {(tm.execution_id || tm.external_id || tm.started_at) && (
            <div className="rounded-lg border bg-muted/20 p-3.5 space-y-2 text-xs">
              <p className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
                <Flame className="h-3.5 w-3.5 text-destructive" /> Stalled Execution Context
              </p>
              <div className="space-y-1.5 pt-1 border-t border-border/50 text-[11px]">
                {tm.execution_id && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Target Execution:</span>
                    <Link
                      href={`/executions/${tm.execution_id}`}
                      className="font-mono text-primary hover:underline flex items-center gap-1 font-medium"
                    >
                      {tm.external_id || `#${tm.execution_id}`}
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  </div>
                )}
                {tm.started_at && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Execution Started At:</span>
                    <span className="text-foreground font-medium">{formatDateTime(tm.started_at)}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {metricType === "OVERDUE_EXECUTION" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3.5">
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
              <p className="text-xs text-muted-foreground font-medium">Time in Queue</p>
              <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-1 font-mono">
                {formatDurationSeconds(tm.queued_seconds ?? tm.metric_value)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {tm.exceeded_by_seconds !== undefined
                  ? `Exceeded limit by ${formatDurationSeconds(tm.exceeded_by_seconds)}`
                  : "Waiting for worker"}
              </p>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground font-medium">Max Queue Delay</p>
              <p className="text-2xl font-bold text-foreground mt-1 font-mono">
                {formatDurationSeconds(tm.max_queue_delay_seconds)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Buffer: +{Number(tm.threshold ?? alertRule?.threshold ?? 0)}s
              </p>
            </div>
          </div>

          {(tm.execution_id || tm.external_id || tm.created_at) && (
            <div className="rounded-lg border bg-muted/20 p-3.5 space-y-2 text-xs">
              <p className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
                <Hourglass className="h-3.5 w-3.5 text-amber-500" /> Pending Task Context
              </p>
              <div className="space-y-1.5 pt-1 border-t border-border/50 text-[11px]">
                {tm.execution_id && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Pending Execution:</span>
                    <Link
                      href={`/executions/${tm.execution_id}`}
                      className="font-mono text-primary hover:underline flex items-center gap-1 font-medium"
                    >
                      {tm.external_id || `#${tm.execution_id}`}
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  </div>
                )}
                {tm.created_at && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Enqueued At:</span>
                    <span className="text-foreground font-medium">{formatDateTime(tm.created_at)}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {(metricType === "FAILURE_RATE_ANOMALY" || metricType === "RETRY_RATE_ANOMALY") && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3">
              <p className="text-xs text-muted-foreground font-medium">Observed Rate</p>
              <p className="text-2xl font-bold text-destructive mt-1 font-mono">
                {tm.current_value !== undefined ? `${Number(tm.current_value).toFixed(1)}%` : "–"}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">In current 60m window</p>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground font-medium">Historical Baseline</p>
              <p className="text-2xl font-bold text-foreground mt-1 font-mono">
                {tm.baseline_value !== undefined ? `${Number(tm.baseline_value).toFixed(1)}%` : "–"}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">7-day median baseline</p>
            </div>
            <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-3">
              <p className="text-xs text-purple-700 dark:text-purple-300 font-medium">Deviation Factor</p>
              <p className="text-2xl font-bold text-purple-700 dark:text-purple-300 mt-1 font-mono">
                {tm.deviation_ratio !== undefined ? `${tm.deviation_ratio}×` : "–"}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Adaptive limit: {tm.adaptive_threshold !== undefined ? `${tm.adaptive_threshold}%` : "3× baseline"}
              </p>
            </div>
          </div>

          <div className="rounded-lg border bg-muted/20 p-3.5 space-y-2 text-xs">
            <p className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
              <Sparkles className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400" /> Statistical Baseline Parameters
            </p>
            <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border/50 text-[11px]">
              <div>
                <span className="text-muted-foreground">Sample Size: </span>
                <strong className="text-foreground font-medium">{tm.sample_count ?? "–"} runs in window</strong>
              </div>
              <div>
                <span className="text-muted-foreground">Observation Window: </span>
                <strong className="text-foreground font-medium">{tm.observation_window_minutes ?? 60} minutes</strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {metricType === "DURATION_ANOMALY" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3">
              <p className="text-xs text-muted-foreground font-medium">Observed P95</p>
              <p className="text-2xl font-bold text-destructive mt-1 font-mono">
                {formatDurationMs(tm.current_value)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">In current 60m window</p>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground font-medium">Historical Baseline</p>
              <p className="text-2xl font-bold text-foreground mt-1 font-mono">
                {formatDurationMs(tm.baseline_value)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">7-day P95 runtime</p>
            </div>
            <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-3">
              <p className="text-xs text-purple-700 dark:text-purple-300 font-medium">Slowdown Factor</p>
              <p className="text-2xl font-bold text-purple-700 dark:text-purple-300 mt-1 font-mono">
                {tm.deviation_ratio !== undefined ? `${tm.deviation_ratio}×` : "–"}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Adaptive limit: {formatDurationMs(tm.adaptive_threshold)}
              </p>
            </div>
          </div>

          <div className="rounded-lg border bg-muted/20 p-3.5 space-y-2 text-xs">
            <p className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
              <Sparkles className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400" /> Statistical Baseline Parameters
            </p>
            <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border/50 text-[11px]">
              <div>
                <span className="text-muted-foreground">Sample Size: </span>
                <strong className="text-foreground font-medium">{tm.sample_count ?? "–"} runs in window</strong>
              </div>
              <div>
                <span className="text-muted-foreground">Observation Window: </span>
                <strong className="text-foreground font-medium">{tm.observation_window_minutes ?? 60} minutes</strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {metricType === "EXECUTION_VOLUME_ANOMALY" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3">
              <p className="text-xs text-muted-foreground font-medium">Window Volume</p>
              <p className="text-2xl font-bold text-destructive mt-1 font-mono">
                {tm.current_value ?? "–"} runs
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">In current 60m window</p>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground font-medium">Historical Baseline</p>
              <p className="text-2xl font-bold text-foreground mt-1 font-mono">
                {tm.baseline_value !== undefined ? `${Number(tm.baseline_value).toFixed(1)}/hr` : "–"}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">Average hourly volume</p>
            </div>
            <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-3">
              <p className="text-xs text-purple-700 dark:text-purple-300 font-medium">Volume Ratio</p>
              <p className="text-2xl font-bold text-purple-700 dark:text-purple-300 mt-1 font-mono">
                {tm.deviation_ratio !== undefined ? `${tm.deviation_ratio}×` : "–"}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Normal range: 0.2× – 4.0×
              </p>
            </div>
          </div>
        </div>
      )}

      {(metricType === "FAILURE_RATE" || metricType === "RETRY_RATE") && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3.5">
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3">
              <p className="text-xs text-muted-foreground font-medium">Observed Rate</p>
              <p className="text-2xl font-bold text-destructive mt-1 font-mono">
                {tm.metric_value !== undefined ? `${Number(tm.metric_value).toFixed(1)}%` : "–"}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Over {tm.window_minutes ?? alertRule?.window_minutes ?? 60}m rolling window
              </p>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground font-medium">Configured Threshold</p>
              <p className="text-2xl font-bold text-foreground mt-1 font-mono">
                ≥ {Number(tm.threshold ?? alertRule?.threshold ?? 0).toFixed(1)}%
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">Violation limit</p>
            </div>
          </div>

          {tm.total_executions !== undefined && (
            <div className="rounded-md border bg-muted/20 p-2.5 text-xs text-muted-foreground flex items-center justify-between">
              <span>Total Executions Evaluated in Window:</span>
              <strong className="text-foreground">{tm.total_executions} runs</strong>
            </div>
          )}
        </div>
      )}

      {metricType === "P95_DURATION" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3.5">
            <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 p-3">
              <p className="text-xs text-muted-foreground font-medium">Observed P95</p>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1 font-mono">
                {formatDurationMs(tm.metric_value)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Slowest 5% in {tm.window_minutes ?? alertRule?.window_minutes ?? 60}m window
              </p>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground font-medium">Configured Threshold</p>
              <p className="text-2xl font-bold text-foreground mt-1 font-mono">
                ≥ {formatDurationMs(tm.threshold ?? alertRule?.threshold)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">Violation limit</p>
            </div>
          </div>

          {tm.total_executions !== undefined && (
            <div className="rounded-md border bg-muted/20 p-2.5 text-xs text-muted-foreground flex items-center justify-between">
              <span>Total Executions Evaluated in Window:</span>
              <strong className="text-foreground">{tm.total_executions} runs</strong>
            </div>
          )}
        </div>
      )}

      {/* Fallback for other / legacy types */}
      {![
        "MISSED_EXECUTION",
        "STALLED_EXECUTION",
        "OVERDUE_EXECUTION",
        "FAILURE_RATE_ANOMALY",
        "RETRY_RATE_ANOMALY",
        "DURATION_ANOMALY",
        "EXECUTION_VOLUME_ANOMALY",
        "FAILURE_RATE",
        "RETRY_RATE",
        "P95_DURATION",
      ].includes(metricType) && (
        <div className="grid grid-cols-2 gap-3.5">
          <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3">
            <p className="text-xs text-muted-foreground font-medium">Actual Value</p>
            <p className="text-2xl font-bold text-destructive mt-1 font-mono">
              {tm.metric_value !== undefined ? tm.metric_value : tm.actual_value ?? "–"}
            </p>
          </div>
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground font-medium">Threshold</p>
            <p className="text-2xl font-bold text-foreground mt-1 font-mono">
              {tm.threshold !== undefined ? tm.threshold : alertRule?.threshold ?? "–"}
            </p>
          </div>
        </div>
      )}

      {/* ── Associated Alert Rule Link ── */}
      <div className="pt-2 border-t flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
        <div>
          <span className="text-muted-foreground">Configured Alert Rule: </span>
          {alertRule ? (
            <Link
              href="/alerts"
              className="text-primary hover:underline font-medium inline-flex items-center gap-1 ml-1"
            >
              <Activity className="h-3 w-3" />
              {getMetricLabel(alertRule.metric)}
              {alertRule.metric.includes("ANOMALY")
                ? " (Auto-tuned)"
                : alertRule.metric === "MISSED_EXECUTION"
                ? ` (+${alertRule.threshold}s buffer)`
                : ` (Threshold: ${alertRule.threshold})`}
            </Link>
          ) : ruleId ? (
            <span className="font-mono text-muted-foreground ml-1">Rule #{ruleId}</span>
          ) : (
            <span className="text-muted-foreground italic ml-1">Automated Reliability Evaluator</span>
          )}
        </div>

        {jobId && (
          <Link
            href={`/jobs/${jobId}/reliability`}
            className="text-primary hover:underline text-[11px] font-medium flex items-center gap-1 shrink-0"
          >
            <History className="h-3 w-3" /> View Job Reliability Activity
          </Link>
        )}
      </div>
    </div>
  );
}
