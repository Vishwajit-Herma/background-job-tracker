"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useWorkspace } from "@/hooks/use-workspace";
import { getJobReliability, ReliabilityState } from "@/lib/api/reliability";
import { JobHeader } from "@/components/bjt/jobs/job-header";
import { ReliabilityBadge } from "@/components/bjt/reliability/reliability-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDurationSeconds, formatReliabilityTime } from "@/lib/reliability-utils";
import { Activity, ShieldCheck, LineChart, Clock, ArrowRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/bjt/states";

interface JobOverviewClientProps {
  jobId: number;
}

export function JobOverviewClient({ jobId }: JobOverviewClientProps) {
  const { jobs, projectMap, isLoading: isLoadingWorkspace } = useWorkspace();

  const {
    data: reliability,
    isLoading: isLoadingReliability,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["job-reliability", jobId],
    queryFn: () => getJobReliability(jobId),
  });

  const job = jobs.find((j) => j.id === jobId);
  const project = job ? projectMap.get(job.project) : null;

  if (isLoadingWorkspace || isLoadingReliability) {
    return (
      <div className="space-y-6 animate-pulse">
        <Skeleton className="h-20 w-full rounded-lg" />
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    );
  }

  if (isError || !reliability) {
    return (
      <div className="space-y-6">
        <ErrorState
          title="Unable to load job overview"
          description="Failed to retrieve job details."
          retry={() => { refetch(); }}
        />
      </div>
    );
  }

  const jobHeaderInfo = {
    id: reliability.job_id,
    name: reliability.job_name,
    task_identifier: reliability.task_identifier,
    status: job?.status || "active",
    operational_status: job?.operational_status,
    reliability_state: (reliability.is_enabled ? reliability.current_state : "DISABLED") as ReliabilityState | "DISABLED",
    project_id: project?.id,
    project_name: project?.name,
  };

  const lastExecTime = formatReliabilityTime(reliability.last_execution_at);
  const nextExpectedTime = formatReliabilityTime(reliability.next_expected_at);

  return (
    <div className="space-y-6">
      <JobHeader job={jobHeaderInfo} />

      {/* Quick Summary Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {/* Reliability State Card */}
        <Card className="border shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center justify-between">
              Reliability State <ShieldCheck className="h-4 w-4 text-primary" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mt-1">
              <ReliabilityBadge
                state={reliability.is_enabled ? reliability.current_state : "DISABLED"}
                jobId={jobId}
                size="lg"
              />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {reliability.active_findings.length} active issue{reliability.active_findings.length === 1 ? "" : "s"}
            </p>
          </CardContent>
        </Card>

        {/* Operational Health Card */}
        <Card className="border shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center justify-between">
              Operational Status <Activity className="h-4 w-4 text-primary" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mt-1">
              {job?.operational_status === "CRITICAL" ? (
                <Badge variant="destructive" className="text-xs">Critical</Badge>
              ) : job?.operational_status === "DEGRADED" ? (
                <Badge variant="warning" className="text-xs">Degraded</Badge>
              ) : (
                <Badge variant="success" className="text-xs">Healthy</Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {job?.active_incidents_count ?? 0} active incident{job?.active_incidents_count === 1 ? "" : "s"}
            </p>
          </CardContent>
        </Card>

        {/* Schedule Cadence */}
        <Card className="border shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center justify-between">
              Schedule Interval <Clock className="h-4 w-4 text-primary" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-bold text-foreground">
              {reliability.expected_interval_seconds
                ? `Every ${formatDurationSeconds(reliability.expected_interval_seconds)}`
                : "Not configured"}
            </p>
            <p className="text-xs text-muted-foreground mt-1 truncate" title={nextExpectedTime.exact}>
              Next: {nextExpectedTime.relative}
            </p>
          </CardContent>
        </Card>

        {/* Total Executions */}
        <Card className="border shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center justify-between">
              Total Runs <LineChart className="h-4 w-4 text-primary" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-bold text-foreground">
              {job?.executions_count?.toLocaleString() || 0}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {job?.success_rate !== null && job?.success_rate !== undefined ? `${job.success_rate}% success` : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Feature Deep Dive Shortcuts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Reliability Card Shortcut */}
        <Card className="border hover:border-primary/50 transition-colors shadow-sm flex flex-col justify-between">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" /> Reliability & Expectations
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              Monitor job schedule adherence, detect silent or stalled runs, inspect statistical baselines, and configure expectations.
            </p>
          </CardHeader>
          <CardContent className="pt-0">
            <Link href={`/jobs/${jobId}/reliability`}>
              <Button variant="secondary" className="w-full justify-between">
                <span>View Job Reliability</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Analytics Card Shortcut */}
        <Card className="border hover:border-primary/50 transition-colors shadow-sm flex flex-col justify-between">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <LineChart className="h-4 w-4 text-primary" /> Job Analytics
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              Analyze throughput trends, failure rates, queue distributions, and P95 latency profiles over time.
            </p>
          </CardHeader>
          <CardContent className="pt-0">
            <Link href={`/jobs/${jobId}/analytics`}>
              <Button variant="secondary" className="w-full justify-between">
                <span>View Analytics</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Executions Card Shortcut */}
        <Card className="border hover:border-primary/50 transition-colors shadow-sm flex flex-col justify-between">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" /> Execution Telemetry
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              Inspect individual execution events, task parameters, return values, errors, retries, and traces.
            </p>
          </CardHeader>
          <CardContent className="pt-0">
            <Link href={`/jobs/${jobId}/executions`}>
              <Button variant="secondary" className="w-full justify-between">
                <span>View Executions</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
