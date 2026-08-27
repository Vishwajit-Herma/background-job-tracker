"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getProjectReliability } from "@/lib/api/reliability";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ReliabilityBadge } from "@/components/bjt/reliability/reliability-badge";
import { ShieldCheck, AlertTriangle, ArrowRight, CheckCircle2, Clock, AlertCircle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface ProjectReliabilitySummaryProps {
  projectId: number;
}

export function ProjectReliabilitySummary({ projectId }: ProjectReliabilitySummaryProps) {
  const { data: reliability, isLoading, isError } = useQuery({
    queryKey: ["project-reliability", projectId],
    queryFn: () => getProjectReliability(projectId),
  });

  if (isLoading) {
    return (
      <div className="border-t pt-4 mt-4 space-y-3 animate-pulse">
        <Skeleton className="h-4 w-36" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !reliability) {
    return null;
  }

  const jobsNeedingAttention = reliability.jobs.filter((j) => j.current_state !== "HEALTHY");

  return (
    <div className="border-t pt-4 mt-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">Reliability Health</span>
          <span className="text-xs text-muted-foreground font-normal">
            ({reliability.total_jobs} monitored job{reliability.total_jobs === 1 ? "" : "s"})
          </span>
        </div>
      </div>

      {/* Aggregate Counts Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="p-3 rounded-lg border bg-emerald-500/5 border-emerald-500/20 flex items-center justify-between">
          <div className="space-y-0.5">
            <span className="text-muted-foreground">Healthy</span>
            <p className="text-lg font-bold text-emerald-700 dark:text-emerald-400">
              {reliability.healthy_jobs_count}
            </p>
          </div>
          <CheckCircle2 className="h-4 w-4 text-emerald-500/60" />
        </div>

        <div className="p-3 rounded-lg border bg-amber-500/5 border-amber-500/20 flex items-center justify-between">
          <div className="space-y-0.5">
            <span className="text-muted-foreground">Missed</span>
            <p className="text-lg font-bold text-amber-700 dark:text-amber-400">
              {reliability.missed_jobs_count}
            </p>
          </div>
          <AlertTriangle className="h-4 w-4 text-amber-500/60" />
        </div>

        <div className="p-3 rounded-lg border bg-destructive/5 border-destructive/20 flex items-center justify-between">
          <div className="space-y-0.5">
            <span className="text-muted-foreground">Stalled</span>
            <p className="text-lg font-bold text-destructive">
              {reliability.stalled_jobs_count}
            </p>
          </div>
          <AlertCircle className="h-4 w-4 text-destructive/60" />
        </div>

        <div className="p-3 rounded-lg border bg-orange-500/5 border-orange-500/20 flex items-center justify-between">
          <div className="space-y-0.5">
            <span className="text-muted-foreground">Overdue</span>
            <p className="text-lg font-bold text-orange-700 dark:text-orange-400">
              {reliability.overdue_jobs_count}
            </p>
          </div>
          <Clock className="h-4 w-4 text-orange-500/60" />
        </div>
      </div>

      {/* Jobs Needing Attention */}
      {jobsNeedingAttention.length > 0 ? (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-900 dark:text-amber-300 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-600" /> Jobs Needing Attention ({jobsNeedingAttention.length})
            </span>
          </div>

          <div className="space-y-2 pt-1">
            {jobsNeedingAttention.map((job) => (
              <div
                key={job.job_id}
                className="flex items-center justify-between p-2 rounded bg-background/80 border text-xs gap-3"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-semibold text-foreground truncate">{job.job_name}</span>
                  <code className="text-[10px] text-muted-foreground font-mono truncate hidden sm:inline-block">
                    {job.task_identifier}
                  </code>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <ReliabilityBadge state={job.current_state} jobId={job.job_id} size="sm" />
                  <Link href={`/jobs/${job.job_id}/reliability`}>
                    <Button variant="ghost" size="sm" className="h-6 px-1.5 text-[11px] gap-1 text-primary">
                      View <ArrowRight className="h-3 w-3" />
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-lg border bg-muted/20 p-2.5 flex items-center justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-medium">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> All {reliability.total_jobs} monitored background jobs are operating normally.
          </span>
        </div>
      )}
    </div>
  );
}
