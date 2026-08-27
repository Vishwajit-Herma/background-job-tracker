"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useJobAnalytics, useJobAnalyticsTrend } from "@/hooks/analytics/use-job-analytics";
import { AnalyticsHeader } from "@/components/bjt/analytics/analytics-header";
import { MetricCard } from "@/components/bjt/analytics/metric-card";
import { HealthCard } from "@/components/bjt/analytics/health-card";
import { ChartSkeleton, MetricCardSkeleton, TableSkeleton } from "@/components/bjt/analytics/skeletons";
import { MultiSeriesChart, TrendLineChart, CHART_COLORS } from "@/components/bjt/analytics/charts";
import { format } from "date-fns";
import { QueueSummaryTable, WorkerSummaryTable } from "@/components/bjt/analytics/summary-tables";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ActivityIcon, CheckCircleIcon, CircleXIcon, ClockIcon, RotateCcwIcon, TriangleAlertIcon, InfoIcon, ArrowLeftIcon, Loader2 as Spinner } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AnalyticsMetricDelta } from "@/lib/api/analytics";


function formatRate(rate: number) {
  return `${rate.toFixed(1)}%`;
}

function formatDuration(ms: number | null) {
  if (ms === null || ms === undefined) return "N/A";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function buildTrend(
  delta?: AnalyticsMetricDelta, 
  positiveDirection: "up" | "down" | "neutral" = "up",
  usePoints: boolean = false,
  formatter: (v: number) => string = (v) => `${v.toFixed(1)}%`
) {
  if (!delta || (usePoints ? delta.delta_points === null : delta.delta_percent === null)) {
    return {
      value: "",
      label: "— No previous-period comparison",
      direction: "neutral" as const,
      isFavorable: true,
      tooltip: "Not enough data in the previous period to compare."
    };
  }

  const val = usePoints ? (delta.delta_points ?? 0) : (delta.delta_percent ?? 0);
  const direction = (val > 0 ? "up" : val < 0 ? "down" : "neutral") as "up" | "down" | "neutral";
  
  let isFavorable = true;
  if (positiveDirection === "up") isFavorable = val >= 0;
  else if (positiveDirection === "down") isFavorable = val <= 0;
  else isFavorable = true;

  return {
    value: formatter(Math.abs(val)),
    label: `vs ${delta.comparison_period}`,
    direction,
    isFavorable,
    tooltip: `Compared with ${delta.comparison_period}`
  };
}

import { JobHeader } from "@/components/bjt/jobs/job-header";
import { useWorkspace } from "@/hooks/use-workspace";

interface JobAnalyticsClientProps {
  jobId: number;
}

export function JobAnalyticsClient({ jobId }: JobAnalyticsClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const range = searchParams.get("range") || "24h";

  const { jobs, projectMap } = useWorkspace();
  const job = jobs.find((j) => j.id === jobId);
  const project = job ? projectMap.get(job.project) : null;

  const { data: analytics, isLoading: isAnalyticsLoading, isError: isAnalyticsError, refetch: refetchAnalytics, isRefetching: isRefetchingAnalytics } = useJobAnalytics(jobId, { range });
  const { data: trendData, isLoading: isTrendLoading, isError: isTrendError, refetch: refetchTrend, isRefetching: isRefetchingTrend } = useJobAnalyticsTrend(jobId, { range });

  const hasDurationData = trendData?.trend.some(t => t.average_duration_ms !== null || t.p95_duration_ms !== null);

  const getXAxisFormatter = (range: string) => {
    if (range === "7d" || range === "30d") {
      return (tick: string) => format(new Date(tick), "MMM d");
    }
    return (tick: string) => format(new Date(tick), "HH:mm");
  };
  const xAxisFormatter = getXAxisFormatter(range);

  const isLoading = isAnalyticsLoading || isTrendLoading;
  const isRefreshing = isRefetchingAnalytics || isRefetchingTrend;

  const handleRefresh = () => {
    refetchAnalytics();
    refetchTrend();
  };

  const jobHeaderInfo = {
    id: jobId,
    name: job?.name || analytics?.job_name || `Job #${jobId}`,
    task_identifier: job?.task_identifier || analytics?.task_identifier || "",
    status: job?.status || "active",
    operational_status: job?.operational_status,
    project_id: project?.id,
    project_name: project?.name,
  };

  return (
    <div className="space-y-6">
      <JobHeader job={jobHeaderInfo} />

      <AnalyticsHeader 
        title={analytics?.job_name || "Job Analytics"} 
        showProjectFilter={false} 
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      {(isAnalyticsError || isTrendError) && (
        <div className="bg-destructive/15 text-destructive p-4 rounded-md flex items-start gap-3">
          <TriangleAlertIcon className="h-5 w-5 mt-0.5" />
          <div>
            <h4 className="font-semibold">Error Loading Data</h4>
            <p className="text-sm">Failed to fetch analytics data for this job. Please try again.</p>
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <div>
          {isAnalyticsLoading || !analytics ? <MetricCardSkeleton /> : (
            <HealthCard health={analytics.health || "HEALTHY"} infoText="Mathematical health based on failure/retry rates in the selected time window (differs from real-time Operational Status which is based on active incidents)." />
          )}
        </div>
        <div>
          {isAnalyticsLoading || !analytics ? <MetricCardSkeleton /> : (
            <MetricCard
              title="Open Incidents"
              infoText="Active alerts requiring attention"
              value={(analytics.open_incidents ?? 0).toLocaleString()}
              icon={TriangleAlertIcon}
              trend={{
                value: analytics.critical_incidents > 0 ? `${analytics.critical_incidents} Critical` : "No Critical",
                direction: "neutral",
                isFavorable: analytics.critical_incidents === 0
              }}
            />
          )}
        </div>
        <div>
          {isAnalyticsLoading || !analytics ? <MetricCardSkeleton /> : (
            <MetricCard
              title="Executions"
              infoText="Total number of times this job was executed"
              value={(analytics.executions?.current ?? 0).toLocaleString()}
              icon={ActivityIcon}
              trend={buildTrend(analytics.executions, "neutral")}
            />
          )}
        </div>
        <div>
          {isAnalyticsLoading || !analytics ? <MetricCardSkeleton /> : (
            <MetricCard
              title="Success Rate"
              infoText="Percentage of executions that completed successfully"
              value={formatRate(analytics.success_rate.current || 0)}
              icon={CheckCircleIcon}
              trend={buildTrend(analytics.success_rate, "up", true)}
            />
          )}
        </div>
        <div>
          {isAnalyticsLoading || !analytics ? <MetricCardSkeleton /> : (
            <MetricCard
              title="Failure Rate"
              infoText="Percentage of executions that failed"
              value={formatRate(analytics.failure_rate.current || 0)}
              icon={CircleXIcon}
              trend={buildTrend(analytics.failure_rate, "down", true)}
            />
          )}
        </div>
        <div>
          {isAnalyticsLoading || !analytics ? <MetricCardSkeleton /> : (
            <MetricCard
              title="Retry Rate"
              infoText="Percentage of executions that experienced at least one retry"
              value={formatRate(analytics.retry_rate.current || 0)}
              icon={RotateCcwIcon}
              trend={buildTrend(analytics.retry_rate, "down", true)}
            />
          )}
        </div>
        <div>
          {isAnalyticsLoading || !analytics ? <MetricCardSkeleton /> : (
            <MetricCard
              title="Average Duration"
              infoText="Mean time taken to complete the job"
              value={formatDuration(analytics.average_duration_ms.current)}
              icon={ClockIcon}
              trend={buildTrend(analytics.average_duration_ms, "down")}
            />
          )}
        </div>
        <div>
          {isAnalyticsLoading || !analytics ? <MetricCardSkeleton /> : (
            <MetricCard
              title="P95 Duration"
              infoText="95% of executions complete faster than this duration"
              value={formatDuration(analytics.p95_duration_ms.current)}
              icon={ClockIcon}
              trend={buildTrend(analytics.p95_duration_ms, "down")}
            />
          )}
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="col-span-2 lg:col-span-1 flex flex-col h-[350px]">
          <CardHeader className="flex flex-row items-center gap-1.5">
            <CardTitle>Executions Trend</CardTitle>
            <div title="Volume of jobs executed over time, broken down by final status" className="cursor-help flex items-center">
              <InfoIcon className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors" />
            </div>
          </CardHeader>
          <CardContent className="flex-1 min-h-[250px]">
            {isTrendLoading || !trendData ? <ChartSkeleton /> : (
              <MultiSeriesChart 
                data={trendData.trend || []} 
                xAxisFormatter={xAxisFormatter}
                type="area"
                series={[
                  { dataKey: "successes", name: "Success", color: CHART_COLORS.success },
                  { dataKey: "failures", name: "Failed", color: CHART_COLORS.failure },
                  { dataKey: "retries", name: "Retry", color: CHART_COLORS.retry, strokeDasharray: "4 4" }
                ]}
              />
            )}
          </CardContent>
        </Card>

        <Card className="col-span-2 lg:col-span-1 flex flex-col h-[350px]">
          <CardHeader className="flex flex-row items-center gap-1.5">
            <CardTitle>Failure Rate Trend</CardTitle>
            <div title="Percentage of jobs failing over time" className="cursor-help flex items-center">
              <InfoIcon className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors" />
            </div>
          </CardHeader>
          <CardContent className="flex-1 min-h-[250px]">
            {isTrendLoading || !trendData ? <ChartSkeleton /> : (
              <TrendLineChart 
                data={trendData.trend || []} 
                dataKey="failure_rate" 
                name="Failure Rate" 
                color={CHART_COLORS.failure} 
                valueFormatter={(v) => v != null ? `${v.toFixed(1)}%` : "0.0%"}
                xAxisFormatter={xAxisFormatter}
                threshold={analytics?.thresholds?.failure_rate !== undefined ? { value: analytics.thresholds.failure_rate, label: "Threshold", color: CHART_COLORS.neutral } : undefined}
              />
            )}
          </CardContent>
        </Card>

        <Card className="col-span-2 lg:col-span-1">
          <CardHeader className="flex flex-row items-center gap-1.5">
            <CardTitle>Duration Trend</CardTitle>
            <div title="Average and P95 job processing times over the selected period" className="cursor-help flex items-center">
              <InfoIcon className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors" />
            </div>
          </CardHeader>
          <CardContent className="h-[300px]">
            {isTrendLoading ? (
              <div className="h-full w-full flex items-center justify-center">
                <Spinner className="h-8 w-8 text-muted-foreground animate-spin" />
              </div>
            ) : !hasDurationData ? (
              <div className="flex h-full items-center justify-center rounded-md border border-dashed bg-muted/20 p-6 text-center text-sm text-muted-foreground">
                <div>
                  <p className="font-medium text-foreground">No duration data available for this period.</p>
                  <p className="mt-1">P95 requires enough completed execution samples.</p>
                </div>
              </div>
            ) : (
              <MultiSeriesChart 
                data={trendData?.trend || []} 
                xAxisFormatter={xAxisFormatter}
                valueFormatter={formatDuration}
                type="line"
                series={[
                  { dataKey: "p95_duration_ms", name: "P95 Duration", color: CHART_COLORS.retry },
                  { dataKey: "average_duration_ms", name: "Average Duration", color: CHART_COLORS.info }
                ]}
              />
            )}
          </CardContent>
        </Card>

        <Card className="col-span-2 lg:col-span-1">
          <CardHeader>
            <CardTitle>Queue Summary</CardTitle>
          </CardHeader>
          <CardContent>
            {isAnalyticsLoading || !analytics || !analytics.queue_summary ? <TableSkeleton /> : (
              <QueueSummaryTable summary={analytics.queue_summary || []} />
            )}
          </CardContent>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Worker Summary</CardTitle>
          </CardHeader>
          <CardContent>
            {isAnalyticsLoading || !analytics || !analytics.worker_summary ? <TableSkeleton /> : (
              <WorkerSummaryTable summary={analytics.worker_summary || []} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
