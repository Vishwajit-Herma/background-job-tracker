"use client";

import { useState } from "react";
import React from "react";
import { useQuery } from "@tanstack/react-query";
import { getExecutions, Execution } from "@/lib/api/executions";
import { useWorkspace } from "@/hooks/use-workspace";
import { JobHeader } from "@/components/bjt/jobs/job-header";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Loader2, Activity, ChevronDown, ChevronRight } from "lucide-react";
import { PaginationControls } from "@/components/bjt/pagination";
import { formatDuration, getStatusBadgeVariant, getStatusIcon, FrameworkBadge } from "@/components/bjt/jobs/executions-sheet";
import { getExecutionEvents } from "@/lib/api/executions";
import { formatReliabilityTime } from "@/lib/reliability-utils";
import { ErrorState } from "@/components/bjt/states";

interface JobExecutionsClientProps {
  jobId: number;
}

function ExecutionDetailsRow({ execution }: { execution: Execution }) {
  const { data: events = [], isLoading } = useQuery({
    queryKey: ["execution-events", execution.id],
    queryFn: () => getExecutionEvents(execution.id),
  });

  return (
    <div className="p-4 bg-muted/20 border-t space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-4">
        <div>
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Framework</p>
          <div className="mt-1"><FrameworkBadge framework={execution.framework} /></div>
        </div>
        <div>
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Worker</p>
          <p className="text-sm font-mono bg-background/50 p-2 rounded border mt-1">{execution.worker || "—"}</p>
        </div>
        <div>
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Queue</p>
          <p className="text-sm font-mono bg-background/50 p-2 rounded border mt-1">{execution.queue || "default"}</p>
        </div>
        <div>
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Retries</p>
          <p className="text-sm bg-background/50 p-2 rounded border mt-1">{execution.retry_count}</p>
        </div>
      </div>

      <h4 className="font-medium text-sm">Event Timeline</h4>
      {isLoading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading event logs...
        </div>
      ) : events.length === 0 ? (
        <p className="text-xs text-muted-foreground">No detailed events found for this execution.</p>
      ) : (
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {events.map((evt) => (
            <div key={evt.id} className="flex items-center justify-between text-xs p-2 rounded bg-background border">
              <span className="font-mono font-semibold uppercase">{evt.status}</span>
              <span className="text-muted-foreground">{new Date(evt.event_timestamp || evt.received_at).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function JobExecutionsClient({ jobId }: JobExecutionsClientProps) {
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { jobs, projectMap, isLoading: isLoadingWorkspace } = useWorkspace();
  const job = jobs.find((j) => j.id === jobId);
  const project = job ? projectMap.get(job.project) : null;

  const {
    data: executionsData,
    isLoading: isLoadingExecutions,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["executions", jobId, page],
    queryFn: () => getExecutions(jobId, { page }),
  });

  const executions = executionsData?.data || [];
  const totalPages = executionsData?.totalPages || 1;

  const jobHeaderInfo = {
    id: jobId,
    name: job?.name || `Job #${jobId}`,
    task_identifier: job?.task_identifier || "",
    status: job?.status || "active",
    operational_status: job?.operational_status,
    project_id: project?.id,
    project_name: project?.name,
  };

  return (
    <div className="space-y-6">
      <JobHeader job={jobHeaderInfo} />

      {isLoadingExecutions || isLoadingWorkspace ? (
        <div className="flex items-center gap-2 text-muted-foreground py-8">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>Loading execution history...</span>
        </div>
      ) : isError ? (
        <ErrorState
          title="Unable to load executions"
          description="Failed to retrieve execution records for this job."
          retry={() => { refetch(); }}
        />
      ) : executions.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center space-y-2 bg-muted/10">
          <Activity className="h-8 w-8 mx-auto text-muted-foreground/40" />
          <h4 className="text-sm font-semibold text-foreground">No executions recorded yet</h4>
          <p className="text-xs text-muted-foreground max-w-sm mx-auto">
            Execution telemetry will appear here once your application starts running background jobs.
          </p>
        </div>
      ) : (
        <div className="rounded-md border bg-card shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10"></TableHead>
                <TableHead>Execution ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Framework</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Queue</TableHead>
                <TableHead>Worker</TableHead>
                <TableHead>Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {executions.map((exec) => {
                const isExpanded = expandedId === exec.id;
                const timeInfo = formatReliabilityTime(exec.started_at || exec.created_at);

                return (
                  <React.Fragment key={exec.id}>
                    <TableRow
                      className="cursor-pointer hover:bg-muted/30"
                      onClick={() => setExpandedId(isExpanded ? null : exec.id)}
                    >
                      <TableCell className="py-2.5">
                        {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </TableCell>
                      <TableCell className="py-2.5 font-mono text-xs">
                        {exec.external_id ? exec.external_id.slice(0, 12) + "..." : `#${exec.id}`}
                      </TableCell>
                      <TableCell className="py-2.5">
                        <div className="flex items-center gap-1.5">
                          {getStatusIcon(exec.status)}
                          <Badge variant={getStatusBadgeVariant(exec.status) as any} className="text-[10px] uppercase font-mono">
                            {exec.status}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="py-2.5">
                        <FrameworkBadge framework={exec.framework} />
                      </TableCell>
                      <TableCell className="py-2.5 text-xs font-mono">
                        {formatDuration(exec.duration_ms)}
                      </TableCell>
                      <TableCell className="py-2.5 text-xs font-mono text-muted-foreground">
                        {exec.queue || "default"}
                      </TableCell>
                      <TableCell className="py-2.5 text-xs text-muted-foreground truncate max-w-[150px]">
                        {exec.worker || "—"}
                      </TableCell>
                      <TableCell className="py-2.5 text-xs text-muted-foreground" title={timeInfo.exact}>
                        {timeInfo.relative}
                      </TableCell>
                    </TableRow>
                    {isExpanded && (
                      <TableRow>
                        <TableCell colSpan={8} className="p-0">
                          <ExecutionDetailsRow execution={exec} />
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                );
              })}
            </TableBody>
          </Table>

          {totalPages > 1 && (
            <div className="px-4 py-3 border-t bg-muted/10">
              <PaginationControls page={page} totalPages={totalPages} setPage={setPage} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
