"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getExecutions, cancelExecution, getExecutionEvents, Execution } from "@/lib/api/executions";
import { getJobs, Job } from "@/lib/api/jobs";
import { getProjects, Project } from "@/lib/api/projects";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, Activity, Briefcase, ListChecks, ChevronDown } from "lucide-react";
import { getStatusBadgeVariant, getStatusIcon, formatDuration, FrameworkBadge } from "@/components/bjt/jobs/executions-sheet";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { AlertCircle, Server, AlertTriangle, CheckCircle2, RotateCw, XCircle, Clock, ChevronRight, ChevronLeft, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PaginationControls } from "@/components/bjt/pagination";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search } from "lucide-react";
import { useDebounce } from "@/hooks/use-debounce";
import { toastError, toastSuccess } from "@/lib/toast";

// Inline subset of ExecutionDetails to show when row is expanded
function StandaloneExecutionDetails({ execution }: { execution: Execution }) {
  const { data: events = [], isLoading } = useQuery({
    queryKey: ["execution-events", execution.id],
    queryFn: () => getExecutionEvents(execution.id),
  });

  const displayEvents = [...events];
  const lastEvent = displayEvents[displayEvents.length - 1];
  const isTerminal = ["failed", "cancelled", "success"].includes(execution.status);

  if (isTerminal && (!lastEvent || lastEvent.status !== execution.status)) {
    displayEvents.push({
      id: -999,
      execution: execution.id,
      event_id: `derived-${execution.status}`,
      status: execution.status,
      event_timestamp: execution.finished_at || execution.updated_at || new Date().toISOString(),
      received_at: execution.updated_at || new Date().toISOString(),
      started_at: execution.started_at,
      finished_at: execution.finished_at,
      duration_ms: execution.duration_ms,
      queue: execution.queue,
      worker: execution.worker,
      retry_count: execution.retry_count,
      error_type: execution.error_type || "",
      error_message: execution.error_message || "",
      traceback: execution.traceback || "",
      metadata: {},
    });
  }

  return (
    <div className="p-4 bg-muted/20 border-t space-y-4">
      {/* Failure / Cancellation Reason Info */}
      {(execution.error_message || execution.error_type) && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3.5 space-y-2 mb-4">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
            <div>
              <h4 className="font-medium text-xs text-destructive uppercase tracking-wide">
                {execution.error_type || (execution.status === "cancelled" ? "Cancellation Reason" : "Failure Reason")}
              </h4>
              <p className="text-xs text-destructive/90 mt-1 font-medium whitespace-pre-wrap">{execution.error_message}</p>
            </div>
          </div>
          {execution.traceback && (
            <div className="mt-2">
              <p className="text-[11px] font-semibold text-muted-foreground uppercase mb-1">Traceback</p>
              <pre className="p-2.5 bg-background rounded border overflow-x-auto text-[11px] text-muted-foreground whitespace-pre-wrap">
                {execution.traceback}
              </pre>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <div className="min-w-0 flex flex-col space-y-1.5">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Framework</p>
          <div className="mt-1">
            <FrameworkBadge framework={execution.framework} />
          </div>
        </div>
        <div className="min-w-0 flex flex-col space-y-1.5">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Worker</p>
          <p className="text-sm break-words leading-relaxed text-foreground bg-background/50 p-2 rounded border">
            {execution.worker || "-"}
          </p>
        </div>
        <div className="min-w-0 flex flex-col space-y-1.5">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Queue</p>
          <p className="text-sm font-mono break-words leading-relaxed text-foreground bg-background/50 p-2 rounded border">
            {execution.queue || "default"}
          </p>
        </div>
        <div className="min-w-0 flex flex-col space-y-1.5">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Retries</p>
          <p className="text-sm leading-relaxed text-foreground bg-background/50 p-2 rounded border">
            {execution.retry_count}
          </p>
        </div>
        {execution.metadata && Object.keys(execution.metadata).length > 0 && (
          <div className="col-span-full">
            <p className="text-xs font-semibold text-muted-foreground uppercase mb-1">Metadata Payload</p>
            <pre className="p-2 bg-background border rounded text-xs overflow-x-auto max-h-32 text-muted-foreground">
              {JSON.stringify(execution.metadata, null, 2)}
            </pre>
          </div>
        )}
      </div>

      <h4 className="font-medium text-sm mb-3">Event Timeline</h4>
      {isLoading ? (
        <div className="flex justify-center py-4"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
      ) : displayEvents.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">No events recorded.</p>
      ) : (
        <div className="space-y-4">
          {displayEvents.map((event, i) => (
            <div key={event.id} className="flex gap-3 relative">
              {i < displayEvents.length - 1 && (
                <div className="absolute left-2 top-6 bottom-[-16px] w-px bg-border" />
              )}
              <div className="h-4 w-4 rounded-full bg-background border flex items-center justify-center shrink-0 mt-0.5 z-10">
                <div className={`h-2 w-2 rounded-full ${event.status === "success" ? "bg-green-500" : event.status === "failed" || event.status === "cancelled" ? "bg-destructive" : "bg-primary"}`} />
              </div>
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
  );
}

export default function ExecutionsPage() {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [page, setPage] = useState(1);

  // Fetch contextual data to display nice names
  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: () => getProjects(),
  });
  
  const { data: jobs = [] } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => getJobs(),
  });

  const projectMap = new Map<number, Project>(projects.map((p) => [p.id, p]));
  const jobMap = new Map<number, Job>(jobs.map((j) => [j.id, j]));

  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const [statusFilter, setStatusFilter] = useState("all");
  const debouncedSearch = useDebounce(search, 500);

  // Fetch executions with pagination
  const { data: paginatedExecutions, isLoading, isError, refetch } = useQuery({
    queryKey: ["executions-all", page, debouncedSearch, ordering, statusFilter],
    queryFn: () => getExecutions(undefined, { page, search: debouncedSearch, ordering, status: statusFilter !== "all" ? statusFilter : undefined }),
  });

  const [cancellingId, setCancellingId] = useState<number | null>(null);

  const handleCancelExecution = async (e: React.MouseEvent, executionId: number) => {
    e.stopPropagation();
    try {
      setCancellingId(executionId);
      await cancelExecution(executionId);
      toastSuccess("Execution cancelled successfully");
      refetch();
    } catch (err: any) {
      toastError("Failed to cancel execution", err);
    } finally {
      setCancellingId(null);
    }
  };

  const executions = paginatedExecutions?.data || [];
  const totalPages = paginatedExecutions?.totalPages || 1;

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Executions</h2>
          <p className="text-muted-foreground mt-1">
            Global view of recent job executions across all your projects.
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-card p-3 rounded-md border">
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search executions by ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="flex w-full sm:w-auto gap-3">
          <div className="w-full sm:w-40">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Status">
                  {statusFilter === "all" && "All Statuses"}
                  {statusFilter === "success" && "Success"}
                  {statusFilter === "failed" && "Failed"}
                  {statusFilter === "running" && "Running"}
                  {statusFilter === "pending" && "Pending"}
                  {statusFilter === "retry" && "Retry"}
                  {statusFilter === "cancelled" && "Cancelled"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="retry">Retry</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-48">
            <Select value={ordering} onValueChange={setOrdering}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Sort by">
                  {ordering === "-created_at" && "Newest First"}
                  {ordering === "created_at" && "Oldest First"}
                  {ordering === "-started_at" && "Recently Started"}
                  {ordering === "-duration_ms" && "Longest Duration"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="-created_at">Newest First</SelectItem>
                <SelectItem value="created_at">Oldest First</SelectItem>
                <SelectItem value="-started_at">Recently Started</SelectItem>
                <SelectItem value="-duration_ms">Longest Duration</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground py-4">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Loading executions...</span>
        </div>
      ) : isError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-destructive">
          Failed to load executions. <button onClick={() => refetch()} className="underline font-medium">Retry</button>
        </div>
      ) : executions.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 rounded-xl border border-dashed text-muted-foreground text-sm">
          <Activity className="h-10 w-10 mb-4 opacity-20" />
          <p>No executions found.</p>
        </div>
      ) : (
        <div className="rounded-md border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40px]"></TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Job / Project</TableHead>
                <TableHead>Framework</TableHead>
                <TableHead>External ID</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Finished</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {executions.map((execution) => {
                const isExpanded = expandedId === execution.id;
                const job = jobMap.get(execution.job as number);
                const project = job ? projectMap.get(job.project as number) : null;
                const isCancellable = execution.status === "running" || execution.status === "pending";
                
                return (
                  <React.Fragment key={execution.id}>
                    <TableRow className={`cursor-pointer hover:bg-muted/50 transition-colors ${isExpanded ? "bg-muted/30" : ""}`} onClick={() => setExpandedId(isExpanded ? null : execution.id)}>
                      <TableCell className="p-3">
                        <ChevronRight className={`h-4 w-4 text-muted-foreground transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                      </TableCell>
                      <TableCell className="py-3">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(execution.status)}
                          <span className="font-medium capitalize text-sm">{execution.status}</span>
                        </div>
                      </TableCell>
                      <TableCell className="py-3">
                        <div className="flex flex-col">
                          <span className="font-medium text-sm flex items-center gap-1.5">
                            <ListChecks className="h-3 w-3 text-muted-foreground" />
                            {job?.name || `Job #${execution.job}`}
                          </span>
                          <span className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                            <Briefcase className="h-3 w-3" />
                            {project?.name || "Unknown Project"}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="py-3">
                        <FrameworkBadge framework={execution.framework} />
                      </TableCell>
                      <TableCell className="py-3">
                        <div className="flex items-center gap-1.5 group">
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono truncate max-w-[120px] inline-block" title={execution.external_id}>
                            {execution.external_id}
                          </code>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigator.clipboard.writeText(execution.external_id);
                            }}
                            className="opacity-0 group-hover:opacity-100 p-1 hover:bg-muted rounded text-muted-foreground transition-opacity"
                            title="Copy full ID"
                          >
                            <Copy className="h-3 w-3" />
                          </button>
                        </div>
                      </TableCell>
                      <TableCell className="py-3 text-sm text-muted-foreground">
                        {formatDuration(execution.duration_ms)}
                      </TableCell>
                      <TableCell className="py-3 text-sm text-muted-foreground">
                        {execution.started_at ? new Date(execution.started_at).toLocaleString() : "-"}
                      </TableCell>
                      <TableCell className="py-3 text-sm text-muted-foreground">
                        {execution.finished_at ? new Date(execution.finished_at).toLocaleString() : "-"}
                      </TableCell>
                      <TableCell className="py-3 text-right">
                        {isCancellable && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={cancellingId === execution.id}
                            onClick={(e) => handleCancelExecution(e, execution.id)}
                            className="h-7 text-xs gap-1 shadow-none hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30"
                          >
                            {cancellingId === execution.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <XCircle className="h-3 w-3 text-destructive" />
                            )}
                            {cancellingId === execution.id ? "Cancelling..." : "Cancel"}
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                    
                    {isExpanded && (
                      <TableRow>
                        <TableCell colSpan={9} className="p-0 border-b">
                          <StandaloneExecutionDetails execution={execution} />
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
              <PaginationControls
                page={page}
                totalPages={totalPages}
                setPage={setPage}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
