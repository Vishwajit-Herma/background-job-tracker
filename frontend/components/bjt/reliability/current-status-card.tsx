"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { JobReliabilityOverview } from "@/lib/api/reliability";
import { ReliabilityBadge } from "./reliability-badge";
import { formatDurationMs, formatDurationSeconds, formatReliabilityTime } from "@/lib/reliability-utils";
import { Activity, Clock, ShieldOff, AlertTriangle, CalendarClock, Timer, CheckCircle2, HeartPulse } from "lucide-react";
import { cn } from "@/lib/utils";

function formatSeconds(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${Math.round(seconds % 60)}s`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${minutes % 60}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

interface CurrentStatusCardProps {
  reliability: JobReliabilityOverview;
}

export function CurrentStatusCard({ reliability }: CurrentStatusCardProps) {
  const isEnabled = reliability.is_enabled;
  const state = isEnabled ? reliability.current_state : "DISABLED";

  const lastExecTime = formatReliabilityTime(reliability.last_execution_at);
  const nextExpectedTime = formatReliabilityTime(reliability.next_expected_at);
  const missedAfterTime = formatReliabilityTime(reliability.missed_after_at);

  const isMissed = isEnabled && reliability.current_state === "MISSED";
  const overdueSeconds = reliability.overdue_by_seconds;

  return (
    <Card className="shadow-sm border-border/80 h-full flex flex-col justify-between">
      <CardHeader className="pb-3 border-b bg-muted/20">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" /> Current Status
          </CardTitle>
          <ReliabilityBadge state={state} size="lg" clickable={false} />
        </div>
      </CardHeader>

      <CardContent className="pt-4 space-y-4 flex-1">
        {/* Status Explanation */}
        {!isEnabled ? (
          <div className="rounded-lg border border-border bg-muted/40 p-3.5 flex items-start gap-3 text-sm">
            <ShieldOff className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-foreground">Reliability checks are disabled</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Enable monitoring in the Execution Expectations settings to track missed, stalled, and overdue executions.
              </p>
            </div>
          </div>
        ) : isMissed ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3.5 flex items-start gap-3 text-sm">
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div>
              <div className="flex items-center gap-2">
                <p className="font-medium text-amber-900 dark:text-amber-200">Missed expected execution</p>
                {overdueSeconds > 0 && (
                  <Badge variant="warning" className="text-[10px] px-1.5 py-0 h-4">
                    Overdue by {formatDurationSeconds(overdueSeconds)}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-amber-700 dark:text-amber-300/90 mt-0.5">
                The expected execution cutoff has passed without a new execution event being reported.
              </p>
            </div>
          </div>
        ) : reliability.current_state === "STALLED" ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3.5 flex items-start gap-3 text-sm">
            <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-destructive">Execution runtime limit exceeded</p>
              <p className="text-xs text-destructive/90 mt-0.5">
                A running execution has exceeded the configured maximum runtime limit.
              </p>
            </div>
          </div>
        ) : reliability.current_state === "OVERDUE" ? (
          <div className="rounded-lg border border-orange-500/30 bg-orange-500/10 p-3.5 flex items-start gap-3 text-sm">
            <Clock className="h-5 w-5 text-orange-600 dark:text-orange-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-orange-900 dark:text-orange-200">Execution queued longer than limit</p>
              <p className="text-xs text-orange-700 dark:text-orange-300/90 mt-0.5">
                A pending execution has remained in queue longer than the allowed queue delay limit.
              </p>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3.5 flex items-start gap-3 text-sm">
            <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-emerald-900 dark:text-emerald-200">Operating within expected behavior</p>
              <p className="text-xs text-emerald-700 dark:text-emerald-300/90 mt-0.5">
                The job is currently executing on schedule and within expected runtime thresholds.
              </p>
            </div>
          </div>
        )}

        {/* Recovery Velocity Metrics (MTTR / MTBF) */}
        <div className="grid grid-cols-2 gap-3 pt-1">
          <div className="p-3 rounded-lg border bg-card/60">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span className="font-medium uppercase text-[10px] tracking-wider">MTTR (Mean Time to Resolve)</span>
              <Timer className="h-3.5 w-3.5 text-primary" />
            </div>
            <p className="text-base font-bold font-mono text-foreground">
              {formatSeconds(reliability.mttr_seconds)}
            </p>
            <p className="text-[10px] text-muted-foreground">Incident resolution velocity</p>
          </div>

          <div className="p-3 rounded-lg border bg-card/60">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span className="font-medium uppercase text-[10px] tracking-wider">MTBF (Mean Time Between Failures)</span>
              <HeartPulse className="h-3.5 w-3.5 text-emerald-500" />
            </div>
            <p className="text-base font-bold font-mono text-foreground">
              {formatSeconds(reliability.mtbf_seconds)}
            </p>
            <p className="text-[10px] text-muted-foreground">Failure frequency interval</p>
          </div>
        </div>

        {/* Schedule Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1 border-t">
          {/* Last Execution */}
          <div className="p-3 rounded-lg border bg-card/60">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
              <Clock className="h-3.5 w-3.5" /> Last Execution
            </div>
            <p className="text-sm font-semibold text-foreground truncate" title={lastExecTime.exact}>
              {lastExecTime.relative}
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5 truncate" title={lastExecTime.exact}>
              {lastExecTime.exact}
            </p>
          </div>

          {/* Next Expected */}
          <div className="p-3 rounded-lg border bg-card/60">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
              <CalendarClock className="h-3.5 w-3.5" /> Next Expected
            </div>
            <p className="text-sm font-semibold text-foreground truncate" title={nextExpectedTime.exact}>
              {nextExpectedTime.relative}
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5 truncate" title={nextExpectedTime.exact}>
              {nextExpectedTime.exact}
            </p>
          </div>

          {/* Missed After */}
          <div className="p-3 rounded-lg border bg-card/60">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
              <Timer className="h-3.5 w-3.5" /> Missed After (Grace)
            </div>
            <p
              className={cn(
                "text-sm font-semibold truncate",
                isMissed ? "text-amber-600 dark:text-amber-400" : "text-foreground"
              )}
              title={missedAfterTime.exact}
            >
              {missedAfterTime.relative}
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5 truncate" title={missedAfterTime.exact}>
              {missedAfterTime.exact}
            </p>
          </div>
        </div>

        {/* Latest Execution Sub-bar */}
        {reliability.latest_execution && (
          <div className="pt-2 border-t flex flex-wrap items-center justify-between text-xs text-muted-foreground gap-2">
            <div className="flex items-center gap-2">
              <span>Latest Run #{reliability.latest_execution.id}:</span>
              <Badge
                variant={
                  reliability.latest_execution.status === "success"
                    ? "success"
                    : reliability.latest_execution.status === "failure"
                    ? "destructive"
                    : "secondary"
                }
                className="text-[10px] uppercase font-mono px-1.5 py-0"
              >
                {reliability.latest_execution.status}
              </Badge>
            </div>
            <div>
              Runtime: <span className="font-medium text-foreground">{formatDurationMs(reliability.latest_execution.duration_ms)}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
