"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getRecommendedRunbooks,
  getRunbookExecutions,
  executeRunbook,
  Runbook,
  RunbookExecution,
} from "@/lib/api/incidents";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RunbookExecutionCard } from "./runbook-execution-card";
import { RunbookFormDialog } from "./runbook-form-dialog";
import { toastError, toastSuccess } from "@/lib/toast";
import {
  BookOpen,
  Play,
  Loader2,
  ChevronDown,
  ChevronUp,
  Zap,
  Clock,
  ListChecks,
  BookMarked,
  Plus,
} from "lucide-react";

interface RecommendedRunbooksProps {
  incidentId: number;
  projectId?: number;
  jobId?: number | null;
  triggerType?: string | null;
}

function RunbookCard({
  runbook,
  onExecute,
  isPending,
}: {
  runbook: Runbook;
  onExecute: (id: number) => void;
  isPending: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3 shadow-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <BookMarked className="h-4 w-4 text-primary shrink-0" />
            <p className="font-medium text-sm">{runbook.name}</p>
            {runbook.trigger_type ? (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {runbook.trigger_type.replace(/_/g, " ")}
              </Badge>
            ) : (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                Manual / Generic
              </Badge>
            )}
            {(runbook.priority !== undefined && runbook.priority <= 2) || (runbook.match_priority !== undefined && runbook.match_priority <= 2) ? (
              <Badge className="bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20 text-[10px] px-1.5 py-0 gap-1">
                <Zap className="h-2.5 w-2.5" /> High Priority Match
              </Badge>
            ) : null}
          </div>
          {runbook.description && (
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{runbook.description}</p>
          )}
          {runbook.match_reason && (
            <p className="text-xs text-primary/90 mt-1 italic">💡 {runbook.match_reason}</p>
          )}
          <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <ListChecks className="h-3 w-3" />
              {runbook.steps.length} step{runbook.steps.length !== 1 ? "s" : ""}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {runbook.steps.length > 0 && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs gap-1"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              Steps
            </Button>
          )}
          <Button
            size="sm"
            className="h-7 text-xs gap-1"
            onClick={() => onExecute(runbook.id)}
            disabled={isPending}
          >
            {isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            Execute
          </Button>
        </div>
      </div>

      {expanded && runbook.steps.length > 0 && (
        <div className="border-t pt-3 space-y-1.5">
          {runbook.steps.map((step, i) => (
            <div key={step.id || i} className="flex items-start gap-2 text-xs text-muted-foreground">
              <span className="font-mono shrink-0 mt-0.5">{i + 1}.</span>
              <div>
                <span className="font-medium text-foreground">{step.title}</span>
                {step.description && <span className="ml-1">— {step.description}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function RecommendedRunbooks({
  incidentId,
  projectId,
  jobId,
  triggerType,
}: RecommendedRunbooksProps) {
  const queryClient = useQueryClient();
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const { data: recommended = [], isLoading: isLoadingRec } = useQuery({
    queryKey: ["recommended-runbooks", incidentId],
    queryFn: () => getRecommendedRunbooks(incidentId),
    enabled: !!incidentId,
  });

  const { data: executions = [], isLoading: isLoadingExec } = useQuery({
    queryKey: ["runbook-executions", incidentId],
    queryFn: () => getRunbookExecutions(incidentId),
    enabled: !!incidentId,
    refetchInterval: (data) => {
      const list = (data?.state?.data as RunbookExecution[] | undefined) ?? [];
      return list.some((e) => e.status === "IN_PROGRESS") ? 5000 : false;
    },
  });

  const executeMutation = useMutation({
    mutationFn: (runbookId: number) => executeRunbook(incidentId, runbookId),
    onSuccess: () => {
      toastSuccess("Runbook Execution Started");
      queryClient.invalidateQueries({ queryKey: ["runbook-executions", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
    },
    onError: (err: any) => toastError("Failed to execute runbook", err),
  });

  // Build a map from runbook ID to Runbook for execution cards
  const runbookMap = new Map<number, Runbook>();
  recommended.forEach((r) => runbookMap.set(r.id, r));

  const activeExecutions = executions.filter((e) => e.status === "IN_PROGRESS");
  const historicalExecutions = executions.filter((e) => e.status !== "IN_PROGRESS");

  if (isLoadingRec || isLoadingExec) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading runbook data…
      </div>
    );
  }

  const getRunbookForExecution = (execution: RunbookExecution): Runbook => {
    return (
      execution.runbook_details ||
      runbookMap.get(execution.runbook) || {
        id: execution.runbook,
        project: projectId || 0,
        job: jobId || null,
        name: execution.runbook_name || `Runbook #${execution.runbook}`,
        description: "",
        trigger_type: null,
        is_active: true,
        steps: [],
        created_at: "",
        updated_at: "",
      }
    );
  };

  return (
    <div className="space-y-6">
      {/* Response Header Actions */}
      <div className="flex items-center justify-between pb-2 border-b">
        <div>
          <h3 className="font-semibold text-base flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" /> Incident Response Runbooks
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Execute standard operating procedures to resolve this incident or create a new SOP.
          </p>
        </div>
        <Button size="sm" variant="outline" className="h-8 text-xs gap-1.5" onClick={() => setIsCreateOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> Create Runbook
        </Button>
      </div>

      {/* Active Executions */}
      {activeExecutions.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold flex items-center gap-2">
            <Loader2 className="h-4 w-4 text-blue-500 animate-spin" /> Active Executions
          </h4>
          {activeExecutions.map((execution) => (
            <RunbookExecutionCard
              key={execution.id}
              execution={execution}
              runbook={getRunbookForExecution(execution)}
              incidentId={incidentId}
            />
          ))}
        </div>
      )}

      {/* Recommended Runbooks */}
      {recommended.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" /> Recommended Runbooks ({recommended.length})
          </h4>
          {recommended.map((runbook) => (
            <RunbookCard
              key={runbook.id}
              runbook={runbook}
              onExecute={(id) => executeMutation.mutate(id)}
              isPending={executeMutation.isPending && executeMutation.variables === runbook.id}
            />
          ))}
        </div>
      )}

      {recommended.length === 0 && activeExecutions.length === 0 && (
        <div className="flex flex-col items-center justify-center h-48 text-center p-6 rounded-xl border border-dashed bg-muted/10 space-y-3">
          <BookOpen className="h-8 w-8 text-muted-foreground/40" />
          <div>
            <p className="text-sm font-medium">No runbooks matched for this incident</p>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
              Create a runbook tailored for this job or failure mode so your team can resolve it faster next time.
            </p>
          </div>
          <Button size="sm" onClick={() => setIsCreateOpen(true)} className="gap-1.5">
            <Plus className="h-3.5 w-3.5" /> Create Runbook for this Incident
          </Button>
        </div>
      )}

      {/* Execution History */}
      {historicalExecutions.length > 0 && (
        <div className="space-y-3 pt-2">
          <h4 className="text-sm font-semibold flex items-center gap-2 text-muted-foreground">
            <Clock className="h-4 w-4" /> Execution History
          </h4>
          {historicalExecutions.map((execution) => (
            <RunbookExecutionCard
              key={execution.id}
              execution={execution}
              runbook={getRunbookForExecution(execution)}
              incidentId={incidentId}
            />
          ))}
        </div>
      )}

      {/* Create Runbook Dialog pre-filled */}
      <RunbookFormDialog
        open={isCreateOpen}
        onOpenChange={setIsCreateOpen}
        initialProjectId={projectId}
        initialJobId={jobId}
        initialTriggerType={triggerType}
      />
    </div>
  );
}
