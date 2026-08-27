import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { FailingJob, SlowJob, AnalyticsQueueSummary, AnalyticsWorkerSummary } from "@/lib/api/analytics";
import Link from "next/link";
import { formatDuration } from "date-fns"; // We might want a custom formatter, let's build a simple one
import { cn } from "@/lib/utils";

function formatMs(ms: number | null) {
  if (ms === null || ms === undefined) return "N/A";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

interface TopFailingJobsListProps {
  jobs: FailingJob[];
}

export function TopFailingJobsList({ jobs }: TopFailingJobsListProps) {
  if (!jobs || jobs.length === 0) {
    return <div className="p-4 text-center text-sm text-muted-foreground border rounded-md">No failing jobs</div>;
  }

  const maxFailures = Math.max(...jobs.map((j) => j.failure_count));

  return (
    <div className="space-y-3">
      {jobs.map((job) => {
        const percentage = maxFailures > 0 ? (job.failure_count / maxFailures) * 100 : 0;
        return (
          <Link key={job.job_id} href={`/jobs/${job.job_id}/analytics`} className="rounded-md border p-3 flex justify-between items-center bg-card hover:bg-muted/50 cursor-pointer group transition-colors">
            <div className="truncate flex-1 pr-4">
              <span className="font-medium group-hover:underline text-sm truncate block">
                {job.name || job.task_identifier}
              </span>
              <div className="text-xs text-muted-foreground truncate flex items-center mt-1">
                <div className="w-16 h-1.5 bg-muted rounded-full mr-2 overflow-hidden shrink-0">
                  <div className="h-full bg-red-500 rounded-full" style={{ width: `${percentage}%` }} />
                </div>
                <span className="truncate">{job.task_identifier}</span>
              </div>
            </div>
            <div className="text-right whitespace-nowrap">
              <div className="font-semibold text-sm text-red-600 dark:text-red-400">
                {job.failure_count.toLocaleString()} failures
              </div>
              <div className="text-xs text-muted-foreground">
                {job.failure_rate.toFixed(1)}% rate
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}


interface SlowestJobsListProps {
  jobs: SlowJob[];
}

export function SlowestJobsList({ jobs }: SlowestJobsListProps) {
  if (!jobs || jobs.length === 0) {
    return <div className="p-4 text-center text-sm text-muted-foreground border rounded-md">No slow jobs</div>;
  }

  const maxDuration = Math.max(...jobs.map((j) => j.average_duration_ms || 0));

  return (
    <div className="space-y-3">
      {jobs.map((job) => {
        const percentage = maxDuration > 0 ? ((job.average_duration_ms || 0) / maxDuration) * 100 : 0;
        return (
          <Link key={job.job_id} href={`/jobs/${job.job_id}/analytics`} className="rounded-md border p-3 flex justify-between items-center bg-card hover:bg-muted/50 cursor-pointer group transition-colors">
            <div className="truncate flex-1 pr-4">
              <span className="font-medium group-hover:underline text-sm truncate block">
                {job.name || job.task_identifier}
              </span>
              <div className="text-xs text-muted-foreground truncate flex items-center mt-1">
                <div className="w-16 h-1.5 bg-muted rounded-full mr-2 overflow-hidden shrink-0">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: `${percentage}%` }} />
                </div>
                <span className="truncate">{job.task_identifier}</span>
              </div>
            </div>
            <div className="text-right whitespace-nowrap">
              <div className="font-semibold text-sm text-amber-600 dark:text-amber-400">
                {formatMs(job.average_duration_ms)} avg
              </div>
              <div className="text-xs text-muted-foreground">
                {formatMs(job.p95_duration_ms)} p95
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}

interface QueueSummaryTableProps {
  summary: AnalyticsQueueSummary[];
}

export function QueueSummaryTable({ summary }: QueueSummaryTableProps) {
  if (!summary || summary.length === 0) {
    return <div className="p-4 text-center text-sm text-muted-foreground border rounded-md">No queue data</div>;
  }

  return (
    <div className="border rounded-md">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Queue</TableHead>
            <TableHead className="text-right">Executions</TableHead>
            <TableHead className="text-right">Failures</TableHead>
            <TableHead className="text-right">Success Rate</TableHead>
            <TableHead className="text-right">Retry Rate</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {summary.map((q) => (
            <TableRow key={q.queue}>
              <TableCell className="font-medium">{q.queue || "default"}</TableCell>
              <TableCell className="text-right">{q.count.toLocaleString()}</TableCell>
              <TableCell className="text-right">
                {q.failures > 0 ? (
                  <span className="text-red-500 font-medium">{q.failures.toLocaleString()}</span>
                ) : (
                  q.failures
                )}
              </TableCell>
              <TableCell className="text-right">{q.success_rate.toFixed(1)}%</TableCell>
              <TableCell className="text-right">{q.retry_rate.toFixed(1)}%</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

interface WorkerSummaryTableProps {
  summary: AnalyticsWorkerSummary[];
}

export function WorkerSummaryTable({ summary }: WorkerSummaryTableProps) {
  if (!summary || summary.length === 0) {
    return <div className="p-4 text-center text-sm text-muted-foreground border rounded-md">No worker data</div>;
  }

  return (
    <div className="border rounded-md">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Worker</TableHead>
            <TableHead className="text-right">Executions</TableHead>
            <TableHead className="text-right">Failures</TableHead>
            <TableHead className="text-right">Success Rate</TableHead>
            <TableHead className="text-right">Retry Rate</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {summary.map((w) => (
            <TableRow key={w.worker}>
              <TableCell className="font-medium">{w.worker}</TableCell>
              <TableCell className="text-right">{w.count.toLocaleString()}</TableCell>
              <TableCell className="text-right">
                {w.failures > 0 ? (
                  <span className="text-red-500 font-medium">{w.failures.toLocaleString()}</span>
                ) : (
                  w.failures
                )}
              </TableCell>
              <TableCell className="text-right">{w.success_rate.toFixed(1)}%</TableCell>
              <TableCell className="text-right">{w.retry_rate.toFixed(1)}%</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
