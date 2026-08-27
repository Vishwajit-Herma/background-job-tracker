"use client";

import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { IncidentImpact } from "@/lib/api/incidents";
import { Activity, Clock, Cpu, Layers, TrendingUp, CheckCircle, AlertTriangle } from "lucide-react";

interface IncidentImpactCardProps {
  impact: IncidentImpact;
}

function formatDuration(seconds?: number) {
  if (!seconds || seconds <= 0) return "< 1m";
  const mins = Math.floor(seconds / 60);
  const hrs = Math.floor(mins / 60);
  const remMins = mins % 60;
  if (hrs > 0) {
    return `${hrs}h ${remMins}m`;
  }
  return `${mins}m`;
}

export function IncidentImpactCard({ impact }: IncidentImpactCardProps) {
  const {
    window_minutes,
    incident_duration_seconds,
    affected_executions_count,
    failures_count,
    retries_count,
    successes_count,
    failure_rate,
    retry_rate,
    affected_jobs,
    affected_workers,
    affected_queues,
    baseline_comparisons,
  } = impact;

  const frMultiplier = baseline_comparisons?.failure_rate_multiplier;
  const rrMultiplier = baseline_comparisons?.retry_rate_multiplier;

  return (
    <Card className="border shadow-sm bg-gradient-to-b from-card to-card/70 flex flex-col justify-between">
      <CardHeader className="pb-3.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="space-y-0.5">
            <CardTitle className="text-base font-semibold flex items-center gap-2 text-foreground">
              <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
                <Activity className="h-4 w-4" />
              </div>
              Impact Analysis
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              Telemetry evaluated across a bounded {window_minutes}m window.
            </CardDescription>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <Badge
              variant="outline"
              className="bg-primary/5 text-primary border-primary/20 text-xs gap-1 px-2 py-0.5 font-medium"
              title={`Analysis sample window: ${window_minutes} minutes`}
            >
              <Clock className="h-3 w-3" />
              Window: {window_minutes}m
            </Badge>

            {incident_duration_seconds !== undefined && (
              <Badge
                variant="outline"
                className="bg-muted/60 text-muted-foreground text-xs gap-1 px-2 py-0.5 font-medium"
                title="Total elapsed incident lifespan"
              >
                Duration: {formatDuration(incident_duration_seconds)}
              </Badge>
            )}

            <Badge variant="secondary" className="text-xs px-2 py-0.5 font-medium">
              {affected_executions_count} Executions
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3.5 pt-0 flex-1">
        {/* Metric Summary 4-Column Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          {/* Failures */}
          <div className="p-3 rounded-xl border bg-card/90 shadow-sm flex flex-col justify-between gap-1.5 relative overflow-hidden">
            <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground">
              <span>Failures</span>
              <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-destructive/10 text-destructive">
                {failure_rate}%
              </span>
            </div>
            <div className="text-2xl font-bold font-mono text-destructive tracking-tight">
              {failures_count}
            </div>
            {frMultiplier && frMultiplier > 1 ? (
              <span className="text-[10px] text-destructive font-semibold flex items-center gap-0.5 leading-none">
                <TrendingUp className="h-3 w-3 inline shrink-0" />
                {frMultiplier}x vs baseline
              </span>
            ) : (
              <span className="text-[10px] text-muted-foreground font-medium leading-none">
                {successes_count} succeeded
              </span>
            )}
          </div>

          {/* Retries */}
          <div className="p-3 rounded-xl border bg-card/90 shadow-sm flex flex-col justify-between gap-1.5 relative overflow-hidden">
            <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground">
              <span>Retries</span>
              <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-700 dark:text-amber-400">
                {retry_rate}%
              </span>
            </div>
            <div className="text-2xl font-bold font-mono text-amber-700 dark:text-amber-400 tracking-tight">
              {retries_count}
            </div>
            {rrMultiplier && rrMultiplier > 1 ? (
              <span className="text-[10px] text-amber-700 dark:text-amber-400 font-semibold flex items-center gap-0.5 leading-none">
                <TrendingUp className="h-3 w-3 inline shrink-0" />
                {rrMultiplier}x vs baseline
              </span>
            ) : (
              <span className="text-[10px] text-muted-foreground font-medium leading-none">
                0% retry penalty
              </span>
            )}
          </div>

          {/* Affected Workers */}
          <Link
            href={affected_workers.length > 0 ? `/executions?search=${encodeURIComponent(affected_workers[0])}` : "/executions"}
            className="p-3 rounded-xl border bg-card/90 shadow-sm flex flex-col justify-between gap-1.5 hover:border-primary/40 hover:bg-muted/30 transition-all group"
          >
            <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground group-hover:text-primary transition-colors">
              <span>Workers</span>
              <Cpu className="h-3.5 w-3.5 text-purple-500" />
            </div>
            <div className="text-2xl font-bold font-mono text-foreground tracking-tight">
              {affected_workers.length}
            </div>
            <p className="text-[10px] font-mono text-muted-foreground truncate leading-none group-hover:underline" title={affected_workers.join(", ")}>
              {affected_workers.length > 0 ? affected_workers[0] : "None"}
            </p>
          </Link>

          {/* Affected Queues */}
          <Link
            href={affected_queues.length > 0 ? `/executions?search=${encodeURIComponent(affected_queues[0])}` : "/executions"}
            className="p-3 rounded-xl border bg-card/90 shadow-sm flex flex-col justify-between gap-1.5 hover:border-primary/40 hover:bg-muted/30 transition-all group"
          >
            <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground group-hover:text-primary transition-colors">
              <span>Queues</span>
              <Layers className="h-3.5 w-3.5 text-amber-500" />
            </div>
            <div className="text-2xl font-bold font-mono text-foreground tracking-tight">
              {affected_queues.length}
            </div>
            <p className="text-[10px] font-mono text-muted-foreground truncate leading-none group-hover:underline" title={affected_queues.join(", ")}>
              {affected_queues.length > 0 ? affected_queues[0] : "None"}
            </p>
          </Link>
        </div>

        {/* Affected Jobs List */}
        {affected_jobs.length > 0 && (
          <div className="space-y-2 pt-1">
            <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              <span>Affected Jobs Breakdown</span>
              <span>{affected_jobs.length} {affected_jobs.length === 1 ? "Job" : "Jobs"}</span>
            </div>

            <div className="divide-y rounded-xl border bg-card/90 shadow-sm overflow-hidden text-xs">
              {affected_jobs.map((job) => {
                const failPct = job.total > 0 ? Math.round((job.failures / job.total) * 100) : 0;
                return (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}/reliability`}
                    className="p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-primary/5 transition-colors group cursor-pointer"
                  >
                    <div className="min-w-0 space-y-0.5">
                      <div className="font-semibold text-foreground group-hover:text-primary transition-colors flex items-center gap-1.5 truncate">
                        <span>{job.name}</span>
                        <span className="text-[10px] text-primary opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
                      </div>
                      <div className="text-[11px] text-muted-foreground font-mono truncate">
                        {job.task_identifier}
                      </div>
                    </div>

                    <div className="flex items-center gap-2.5 shrink-0 self-end sm:self-auto">
                      {/* Mini visual ratio bar */}
                      <div className="hidden sm:flex flex-col items-end gap-0.5">
                        <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-destructive transition-all"
                            style={{ width: `${failPct}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-muted-foreground font-mono">{failPct}% fail</span>
                      </div>

                      {job.failures > 0 ? (
                        <Badge variant="destructive" className="text-xs py-0.5 px-2 font-mono">
                          {job.failures} Failed
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs py-0.5 px-2 font-mono text-emerald-600 border-emerald-500/30 bg-emerald-500/5">
                          0 Failed
                        </Badge>
                      )}

                      <span className="text-muted-foreground font-mono text-xs font-medium">
                        {job.total} total
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
