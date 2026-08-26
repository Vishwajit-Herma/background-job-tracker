"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getExecutions, getExecutionEvents, Execution, ExecutionEvent } from "@/lib/api/executions";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, Activity, Clock, Server, AlertCircle, ChevronRight, AlertTriangle, CheckCircle2, RotateCw, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { PaginationControls } from "@/components/bjt/pagination";

// ─── Status Helpers ───────────────────────────────────────────────────────────

export function getStatusBadgeVariant(status: string) {
  switch (status.toLowerCase()) {
    case "success": return "default";
    case "failed": return "destructive";
    case "running": return "secondary";
    case "pending": return "outline";
    case "retry": return "outline";
    case "cancelled": return "secondary";
    default: return "outline";
  }
}

export function getStatusIcon(status: string) {
  switch (status.toLowerCase()) {
    case "success": return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "failed": return <AlertCircle className="h-4 w-4 text-destructive" />;
    case "running": return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    case "retry": return <RotateCw className="h-4 w-4 text-yellow-500" />;
    case "cancelled": return <XCircle className="h-4 w-4 text-muted-foreground" />;
    default: return <Activity className="h-4 w-4 text-muted-foreground" />;
  }
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "-";
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(2)}s`;
  const m = Math.floor(s / 60);
  const rs = Math.floor(s % 60);
  return `${m}m ${rs}s`;
}

// ─── Execution Details Sub-Panel ──────────────────────────────────────────────

function ExecutionDetails({ execution }: { execution: Execution }) {
  const { data: events = [], isLoading } = useQuery({
    queryKey: ["execution-events", execution.id],
    queryFn: () => getExecutionEvents(execution.id),
  });

  return (
    <div className="mt-4 p-4 rounded-lg bg-muted/30 border space-y-6 animate-in slide-in-from-top-2 duration-200">
      
      {/* Overview Grid */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="space-y-1 min-w-0">
          <p className="text-muted-foreground">External ID</p>
          <code className="px-1.5 py-0.5 rounded bg-muted text-xs break-all inline-block max-w-full">{execution.external_id}</code>
        </div>
        <div className="space-y-1 min-w-0">
          <p className="text-muted-foreground">Worker / Queue</p>
          <div className="min-w-0">
            <div className="flex items-start gap-1.5 min-w-0">
              <Server className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
              <span className="break-all text-sm leading-snug">{execution.worker || "-"}</span>
            </div>
            <p className="font-mono text-[11px] text-muted-foreground break-all mt-1 pl-5">
              Q: {execution.queue || "default"}
            </p>
          </div>
        </div>
        <div className="space-y-1 min-w-0">
          <p className="text-muted-foreground">Started At</p>
          <p className="break-all">{execution.started_at ? new Date(execution.started_at).toLocaleString() : "-"}</p>
        </div>
        <div className="space-y-1 min-w-0">
          <p className="text-muted-foreground">Finished At</p>
          <p className="break-all">{execution.finished_at ? new Date(execution.finished_at).toLocaleString() : "-"}</p>
        </div>
      </div>

      {/* Error Info (if failed) */}
      {(execution.error_message || execution.error_type) && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 space-y-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div>
              <h4 className="font-medium text-destructive">{execution.error_type || "Error"}</h4>
              <p className="text-sm text-destructive/80 mt-1">{execution.error_message}</p>
            </div>
          </div>
          {execution.traceback && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wide">Traceback</p>
              <pre className="p-3 bg-background rounded-md border overflow-x-auto text-xs text-muted-foreground whitespace-pre-wrap">
                {execution.traceback}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Timeline / Events */}
      <div>
        <h4 className="font-medium text-sm mb-3">Event Timeline</h4>
        {isLoading ? (
          <div className="flex justify-center py-4"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
        ) : events.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">No events recorded.</p>
        ) : (
          <div className="space-y-4">
            {events.map((event, i) => (
              <div key={event.id} className="flex gap-3 relative">
                {/* Timeline connecting line */}
                {i < events.length - 1 && (
                  <div className="absolute left-2 top-6 bottom-[-16px] w-px bg-border" />
                )}
                {/* Icon */}
                <div className="h-4 w-4 rounded-full bg-background border flex items-center justify-center shrink-0 mt-0.5 z-10">
                  <div className={`h-2 w-2 rounded-full ${event.status === "success" ? "bg-green-500" : event.status === "failed" ? "bg-destructive" : "bg-primary"}`} />
                </div>
                {/* Content */}
                <div className="flex-1 space-y-1 pb-2 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium capitalize">{event.status}</p>
                    <span className="text-xs text-muted-foreground shrink-0">
                      {new Date(event.event_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </div>
                  {event.error_message && (
                    <p className="text-xs text-destructive break-words whitespace-pre-wrap">{event.error_message}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}

// ─── Executions Sheet ─────────────────────────────────────────────────────────

export function ExecutionsSheet({
  jobId,
  jobName,
  open,
  onOpenChange,
}: {
  jobId: number | null;
  jobName: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [page, setPage] = useState(1);

  const { data: paginatedExecutions, isLoading, isError } = useQuery({
    queryKey: ["executions", jobId, page],
    queryFn: () => getExecutions(jobId!, { page }),
    enabled: !!jobId && open,
  });

  const executions = paginatedExecutions?.data || [];
  const totalPages = paginatedExecutions?.totalPages || 1;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader className="mb-6">
          <SheetTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Executions for {jobName}
          </SheetTitle>
          <SheetDescription>
            Recent runs and telemetry events for this background job.
          </SheetDescription>
        </SheetHeader>

        {isLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-16 rounded-lg bg-muted/30 animate-pulse" />
            ))}
          </div>
        ) : isError ? (
          <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm flex items-center gap-2">
            <AlertCircle className="h-4 w-4" /> Failed to load executions.
          </div>
        ) : executions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
              <Activity className="h-6 w-6 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-medium">No Executions Found</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm">
              We haven't received any telemetry data for this job yet. Ensure your SDK is configured correctly.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {executions.map((execution) => {
              const isExpanded = expandedId === execution.id;
              
              return (
                <div key={execution.id} className={cn(
                  "rounded-lg border transition-all duration-200 overflow-hidden",
                  isExpanded ? "border-primary/50 shadow-sm" : "hover:border-primary/30"
                )}>
                  {/* Summary Row */}
                  <button 
                    onClick={() => setExpandedId(isExpanded ? null : execution.id)}
                    className="w-full flex items-center justify-between p-4 text-left bg-card hover:bg-muted/30 transition-colors"
                  >
                    <div className="flex items-center gap-4 min-w-0">
                      <div className="shrink-0">
                        {getStatusIcon(execution.status)}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium capitalize text-sm">{execution.status}</span>
                          <span className="text-xs text-muted-foreground hidden sm:inline-block truncate max-w-[200px]">
                            {execution.external_id}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {new Date(execution.last_event_at).toLocaleString()}
                          </span>
                          {execution.duration_ms != null && (
                            <span className="flex items-center gap-1">
                              <Activity className="h-3 w-3" />
                              {formatDuration(execution.duration_ms)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3 shrink-0 ml-4">
                      {execution.retry_count > 0 && (
                        <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-normal">
                          {execution.retry_count} retries
                        </Badge>
                      )}
                      <ChevronRight className={cn(
                        "h-4 w-4 text-muted-foreground transition-transform",
                        isExpanded && "rotate-90"
                      )} />
                    </div>
                  </button>

                  {/* Expanded Detail Panel */}
                  {isExpanded && (
                    <div className="px-4 pb-4 bg-card">
                      <ExecutionDetails execution={execution} />
                    </div>
                  )}
                </div>
              );
            })}
            
            {totalPages > 1 && (
              <div className="pt-4 border-t mt-4">
                <PaginationControls
                  page={page}
                  totalPages={totalPages}
                  setPage={setPage}
                  size="sm"
                />
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
