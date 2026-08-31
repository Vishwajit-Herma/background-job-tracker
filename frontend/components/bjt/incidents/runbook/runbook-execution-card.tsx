"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Runbook, RunbookExecution, StepState, RunbookExecutionStatus } from "@/lib/api/incidents";
import { RunbookStepList } from "./runbook-step-list";
import { ChevronDown, ChevronUp, Clock, XCircle, CheckCircle2, Loader2, Play, User } from "lucide-react";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { transitionRunbookStep, updateRunbookExecutionStatus } from "@/lib/api/incidents";
import { toastError, toastSuccess } from "@/lib/toast";

interface RunbookExecutionCardProps {
  execution: RunbookExecution;
  runbook: Runbook;
  incidentId: number;
}

function getStatusBadge(status: RunbookExecutionStatus) {
  switch (status) {
    case "IN_PROGRESS":
      return (
        <Badge className="bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20 gap-1.5">
          <Loader2 className="h-3 w-3 animate-spin" /> In Progress
        </Badge>
      );
    case "COMPLETED":
      return (
        <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 gap-1.5">
          <CheckCircle2 className="h-3 w-3" /> Completed
        </Badge>
      );
    case "CANCELLED":
      return (
        <Badge variant="outline" className="text-muted-foreground gap-1.5">
          <XCircle className="h-3 w-3" /> Cancelled
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function formatDuration(startedAt: string | null, completedAt: string | null) {
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const diffSec = Math.max(0, Math.floor((end - start) / 1000));
  if (diffSec < 60) return `${diffSec}s`;
  const mins = Math.floor(diffSec / 60);
  const secs = diffSec % 60;
  return `${mins}m ${secs}s`;
}

export function RunbookExecutionCard({ execution, runbook, incidentId }: RunbookExecutionCardProps) {
  const [expanded, setExpanded] = useState(true);
  const queryClient = useQueryClient();

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["runbook-executions", incidentId] });
    queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
  };

  const stepMutation = useMutation({
    mutationFn: (payload: { execution_id: number; step_id: string; from_state: StepState; to_state: StepState }) =>
      transitionRunbookStep(incidentId, payload),
    onSuccess: invalidate,
    onError: (err: any) => toastError("Failed to transition step", err),
  });

  const statusMutation = useMutation({
    mutationFn: (newStatus: RunbookExecutionStatus) =>
      updateRunbookExecutionStatus(incidentId, execution.id, newStatus),
    onSuccess: (_, newStatus) => {
      toastSuccess(`Runbook execution ${newStatus.toLowerCase()}`);
      invalidate();
    },
    onError: (err: any) => toastError("Failed to update execution status", err),
  });

  const isTerminal = execution.status === "COMPLETED" || execution.status === "CANCELLED";
  const completedSteps = Object.values(execution.step_states).filter((s) => s === "COMPLETED" || s === "SKIPPED").length;
  const totalSteps = runbook.steps.length;

  return (
    <div className={`rounded-lg border shadow-sm ${isTerminal ? "opacity-80" : "border-blue-500/30"}`}>
      {/* Header */}
      <div className="p-4 flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-sm">{runbook.name}</p>
            {getStatusBadge(execution.status)}
          </div>
          <div className="flex items-center gap-4 mt-1.5 text-xs text-muted-foreground flex-wrap">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {execution.started_at ? new Date(execution.started_at).toLocaleString() : "—"}
            </span>
            {execution.started_by_name && (
              <span className="flex items-center gap-1">
                <User className="h-3 w-3" />
                Started by <span className="font-medium text-foreground">{execution.started_by_name}</span>
              </span>
            )}
            <span>Duration: {formatDuration(execution.started_at, execution.completed_at)}</span>
            {totalSteps > 0 && (
              <span>
                {completedSteps}/{totalSteps} steps done
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {!isTerminal && (
            <>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs gap-1 text-emerald-600 border-emerald-500/30 hover:bg-emerald-500/10"
                disabled={statusMutation.isPending}
                onClick={() => statusMutation.mutate("COMPLETED")}
              >
                <CheckCircle2 className="h-3 w-3" /> Mark Done
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs gap-1 text-destructive border-destructive/30 hover:bg-destructive/10"
                disabled={statusMutation.isPending}
                onClick={() => statusMutation.mutate("CANCELLED")}
              >
                <XCircle className="h-3 w-3" /> Cancel
              </Button>
            </>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {/* Steps */}
      {expanded && runbook.steps.length > 0 && (
        <div className="px-4 pb-4 border-t pt-3">
          <RunbookStepList
            steps={runbook.steps}
            execution={execution}
            onTransition={(stepId, fromState, toState) =>
              stepMutation.mutate({ execution_id: execution.id, step_id: stepId, from_state: fromState, to_state: toState })
            }
            isPending={stepMutation.isPending}
          />
        </div>
      )}
    </div>
  );
}
