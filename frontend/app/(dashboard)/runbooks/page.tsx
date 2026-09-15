"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getRunbooks, deleteRunbook, deactivateRunbook, Runbook } from "@/lib/api/incidents";
import { useWorkspace } from "@/hooks/use-workspace";
import { RunbookFormDialog } from "@/components/bjt/incidents/runbook/runbook-form-dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  BookOpen,
  Plus,
  Search,
  Server,
  Activity,
  Zap,
  ListChecks,
  Pencil,
  Trash2,
  PowerOff,
  Loader2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { toastError, toastSuccess } from "@/lib/toast";
import { useProject } from "@/components/bjt/project-provider";
import { ProjectSelectFilter } from "@/components/bjt/project-select-filter";

export default function RunbooksPage() {
  const queryClient = useQueryClient();
  const { projects, jobs } = useWorkspace();
  const { selectedProjectId } = useProject();

  const [selectedTrigger, setSelectedTrigger] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingRunbook, setEditingRunbook] = useState<Runbook | null>(null);
  const [expandedStepsId, setExpandedStepsId] = useState<number | null>(null);

  const { data: runbooks = [], isLoading } = useQuery({
    queryKey: [
      "runbooks",
      selectedProjectId !== "all" ? Number(selectedProjectId) : undefined,
      selectedTrigger !== "all" ? selectedTrigger : undefined,
      searchQuery,
    ],
    queryFn: () =>
      getRunbooks({
        project: selectedProjectId !== "all" ? Number(selectedProjectId) : undefined,
        trigger_type: selectedTrigger !== "all" ? selectedTrigger : undefined,
        search: searchQuery || undefined,
      }),
    staleTime: 60 * 1000,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteRunbook(id),
    onSuccess: () => {
      toastSuccess("Runbook deleted");
      queryClient.invalidateQueries({ queryKey: ["runbooks"] });
    },
    onError: (err: any) => toastError("Failed to delete runbook", err),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: number) => deactivateRunbook(id),
    onSuccess: () => {
      toastSuccess("Runbook deactivated");
      queryClient.invalidateQueries({ queryKey: ["runbooks"] });
    },
    onError: (err: any) => toastError("Failed to deactivate runbook", err),
  });

  const handleEdit = (runbook: Runbook) => {
    setEditingRunbook(runbook);
    setIsFormOpen(true);
  };

  const handleCreate = () => {
    setEditingRunbook(null);
    setIsFormOpen(true);
  };

  const projectMap = new Map(projects.map((p) => [p.id, p]));
  const jobMap = new Map(jobs.map((j) => [j.id, j]));

  return (
    <div className="flex-1 space-y-6 p-8 pt-6 max-w-7xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-primary" /> Runbooks
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Standard operating procedures (SOPs) and remediation workflows for background job incidents.
          </p>
        </div>
        <Button onClick={handleCreate} className="gap-2 shrink-0">
          <Plus className="h-4 w-4" /> Create Runbook
        </Button>
      </div>

      {/* Filters bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-card p-3 rounded-lg border">
        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          {/* Search */}
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search runbooks…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 text-sm"
            />
          </div>

          {/* Project Filter */}
          <ProjectSelectFilter className="w-full sm:w-44" />

          {/* Trigger Type Filter */}
          <select
            className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm ring-offset-background focus:outline-none focus:ring-1 focus:ring-ring"
            value={selectedTrigger}
            onChange={(e) => setSelectedTrigger(e.target.value)}
          >
            <option value="all">All Triggers</option>
            <option value="FAILURE_RATE_ANOMALY">Failure Rate Anomaly</option>
            <option value="RETRY_RATE_ANOMALY">Retry Rate Anomaly</option>
            <option value="DURATION_ANOMALY">Duration Anomaly</option>
            <option value="EXECUTION_VOLUME_ANOMALY">Execution Volume Anomaly</option>
            <option value="MISSED_EXECUTION">Missed Execution</option>
            <option value="STALLED_EXECUTION">Stalled Execution</option>
            <option value="OVERDUE_EXECUTION">Overdue Execution</option>
          </select>
        </div>

        <span className="text-xs text-muted-foreground self-center">
          {runbooks.length} runbook{runbooks.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Runbooks List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-48 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mr-2" /> Loading runbooks…
        </div>
      ) : runbooks.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-center p-8 border border-dashed rounded-xl bg-muted/10 space-y-3">
          <BookOpen className="h-10 w-10 text-muted-foreground/40" />
          <div>
            <h3 className="font-semibold text-base">No runbooks found</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">
              Create runbooks to give engineers guided steps for quickly resolving incidents and reducing MTTR.
            </p>
          </div>
          <Button onClick={handleCreate} size="sm" className="gap-2 mt-2">
            <Plus className="h-4 w-4" /> Create First Runbook
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {runbooks.map((rb) => {
            const project = projectMap.get(rb.project);
            const job = rb.job ? jobMap.get(rb.job) : null;
            const isExpanded = expandedStepsId === rb.id;

            return (
              <div
                key={rb.id}
                className={`p-5 rounded-xl border bg-card shadow-sm space-y-4 transition-colors ${
                  !rb.is_active ? "opacity-75 bg-muted/20" : ""
                }`}
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-base leading-tight">{rb.name}</h3>
                      {rb.is_active ? (
                        <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-[10px]">
                          Active
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-muted-foreground text-[10px]">
                          Inactive
                        </Badge>
                      )}
                      {rb.trigger_type ? (
                        <Badge variant="secondary" className="text-[10px] gap-1">
                          <Zap className="h-2.5 w-2.5" />
                          {rb.trigger_type.replace(/_/g, " ")}
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px]">
                          Manual / All
                        </Badge>
                      )}
                    </div>

                    {rb.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {rb.description}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 w-8 p-0"
                      title="Edit Runbook"
                      onClick={() => handleEdit(rb)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    {rb.is_active && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0 text-amber-600 hover:text-amber-700"
                        title="Deactivate Runbook"
                        disabled={deactivateMutation.isPending}
                        onClick={() => deactivateMutation.mutate(rb.id)}
                      >
                        <PowerOff className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                      title="Delete Runbook"
                      disabled={deleteMutation.isPending}
                      onClick={() => deleteMutation.mutate(rb.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                {/* Scope & Metadata */}
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground pt-1 border-t">
                  <span className="flex items-center gap-1">
                    <Server className="h-3.5 w-3.5" /> {project?.name || `Project #${rb.project}`}
                  </span>
                  <span className="flex items-center gap-1">
                    <Activity className="h-3.5 w-3.5" /> {job?.name || "All Jobs"}
                  </span>
                  <span className="flex items-center gap-1">
                    <ListChecks className="h-3.5 w-3.5" /> {rb.steps.length} step{rb.steps.length !== 1 ? "s" : ""}
                  </span>
                </div>

                {/* Steps toggle */}
                {rb.steps.length > 0 && (
                  <div className="space-y-2 pt-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 text-xs text-primary p-0 gap-1"
                      onClick={() => setExpandedStepsId(isExpanded ? null : rb.id)}
                    >
                      {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                      {isExpanded ? "Hide Steps" : `View ${rb.steps.length} Steps`}
                    </Button>

                    {isExpanded && (
                      <div className="space-y-1.5 rounded-lg bg-muted/30 p-3 border text-xs">
                        {rb.steps.map((step, i) => (
                          <div key={step.id || i} className="flex items-start gap-2">
                            <span className="font-mono text-muted-foreground shrink-0">{i + 1}.</span>
                            <div>
                              <p className="font-medium text-foreground">{step.title}</p>
                              {step.description && (
                                <p className="text-muted-foreground mt-0.5">{step.description}</p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Form Dialog for Create / Edit */}
      <RunbookFormDialog
        open={isFormOpen}
        onOpenChange={setIsFormOpen}
        runbook={editingRunbook}
        initialProjectId={selectedProjectId !== "all" ? Number(selectedProjectId) : undefined}
      />
    </div>
  );
}
