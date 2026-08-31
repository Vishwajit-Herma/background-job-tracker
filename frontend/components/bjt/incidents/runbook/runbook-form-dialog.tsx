"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createRunbook,
  updateRunbook,
  Runbook,
  RunbookStep,
  RunbookTriggerType,
} from "@/lib/api/incidents";
import { useWorkspace } from "@/hooks/use-workspace";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Plus, Trash2, ArrowUp, ArrowDown, Loader2, BookOpen } from "lucide-react";

const TRIGGER_TYPES: { value: RunbookTriggerType | ""; label: string }[] = [
  { value: "", label: "Any Incident / Manual Only" },
  { value: "FAILURE_RATE_ANOMALY", label: "Failure Rate Anomaly" },
  { value: "RETRY_RATE_ANOMALY", label: "Retry Rate Anomaly" },
  { value: "DURATION_ANOMALY", label: "Duration Anomaly" },
  { value: "EXECUTION_VOLUME_ANOMALY", label: "Execution Volume Anomaly" },
  { value: "MISSED_EXECUTION", label: "Missed Execution" },
  { value: "STALLED_EXECUTION", label: "Stalled Execution" },
  { value: "OVERDUE_EXECUTION", label: "Overdue Execution" },
];

interface RunbookFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  runbook?: Runbook | null;
  initialProjectId?: number;
  initialJobId?: number | null;
  initialTriggerType?: string | null;
  onSuccess?: (runbook: Runbook) => void;
}

export function RunbookFormDialog({
  open,
  onOpenChange,
  runbook,
  initialProjectId,
  initialJobId,
  initialTriggerType,
  onSuccess,
}: RunbookFormDialogProps) {
  const queryClient = useQueryClient();
  const { projects, jobs } = useWorkspace();

  const [projectId, setProjectId] = useState<number | undefined>(
    runbook?.project || initialProjectId || projects[0]?.id
  );
  const [jobId, setJobId] = useState<number | null>(
    runbook?.job ?? (initialJobId || null)
  );
  const [name, setName] = useState(runbook?.name || "");
  const [description, setDescription] = useState(runbook?.description || "");
  const [triggerType, setTriggerType] = useState<string>(
    runbook?.trigger_type || initialTriggerType || ""
  );
  const [isActive, setIsActive] = useState<boolean>(runbook?.is_active ?? true);
  const [steps, setSteps] = useState<RunbookStep[]>(
    runbook?.steps && runbook.steps.length > 0
      ? runbook.steps
      : [
          {
            id: `step_${Date.now()}_1`,
            title: "Check Celery worker status & queue backlog",
            description: "Inspect flower or rabbitmq/redis queues for blocked consumers",
            order: 1,
          },
        ]
  );
  const [error, setError] = useState<string | null>(null);

  // Sync state when dialog opens or runbook changes
  useEffect(() => {
    if (open) {
      setError(null);
      if (runbook) {
        setProjectId(runbook.project);
        setJobId(runbook.job);
        setName(runbook.name);
        setDescription(runbook.description || "");
        setTriggerType(runbook.trigger_type || "");
        setIsActive(runbook.is_active);
        setSteps(runbook.steps.length > 0 ? runbook.steps : [{ id: `step_1`, title: "", order: 1 }]);
      } else {
        setProjectId(initialProjectId || projects[0]?.id);
        setJobId(initialJobId || null);
        setName("");
        setDescription("");
        setTriggerType(initialTriggerType || "");
        setIsActive(true);
        setSteps([
          {
            id: `step_${Date.now()}_1`,
            title: "Investigate root cause and error traces",
            description: "Review recent failed execution traceback",
            order: 1,
          },
        ]);
      }
    }
  }, [open, runbook, initialProjectId, initialJobId, initialTriggerType, projects]);

  const availableJobs = jobs.filter((j) => (projectId ? j.project === projectId : true));

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!projectId) throw new Error("Please select a project.");
      if (!name.trim()) throw new Error("Please provide a runbook name.");
      if (steps.length === 0 || steps.every((s) => !s.title.trim())) {
        throw new Error("Please add at least one step with a title.");
      }

      const formattedSteps = steps
        .filter((s) => s.title.trim())
        .map((s, idx) => ({
          id: s.id || `step_${idx + 1}`,
          title: s.title.trim(),
          description: s.description?.trim() || "",
          order: idx + 1,
        }));

      const payload = {
        project: projectId,
        job: jobId || null,
        name: name.trim(),
        description: description.trim(),
        trigger_type: triggerType || null,
        steps: formattedSteps,
        is_active: isActive,
      };

      if (runbook?.id) {
        return updateRunbook(runbook.id, payload);
      } else {
        return createRunbook(payload);
      }
    },
    onSuccess: (savedRunbook) => {
      queryClient.invalidateQueries({ queryKey: ["runbooks"] });
      queryClient.invalidateQueries({ queryKey: ["recommended-runbooks"] });
      onOpenChange(false);
      if (onSuccess) onSuccess(savedRunbook);
    },
    onError: (err: any) => {
      setError(
        err.response?.data?.job?.[0] ||
          err.response?.data?.name?.[0] ||
          err.response?.data?.error ||
          err.message ||
          "Failed to save runbook."
      );
    },
  });

  const handleAddStep = () => {
    const nextOrder = steps.length + 1;
    setSteps([
      ...steps,
      {
        id: `step_${Date.now()}_${nextOrder}`,
        title: "",
        description: "",
        order: nextOrder,
      },
    ]);
  };

  const handleRemoveStep = (index: number) => {
    if (steps.length <= 1) return;
    const newSteps = steps.filter((_, i) => i !== index);
    setSteps(newSteps.map((s, i) => ({ ...s, order: i + 1 })));
  };

  const handleMoveStep = (index: number, direction: "up" | "down") => {
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= steps.length) return;
    const newSteps = [...steps];
    const temp = newSteps[index];
    newSteps[index] = newSteps[targetIndex];
    newSteps[targetIndex] = temp;
    setSteps(newSteps.map((s, i) => ({ ...s, order: i + 1 })));
  };

  const handleStepChange = (index: number, field: keyof RunbookStep, value: string) => {
    const newSteps = [...steps];
    newSteps[index] = { ...newSteps[index], [field]: value };
    setSteps(newSteps);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-primary" />
            <DialogTitle>{runbook ? "Edit Runbook" : "Create Standard Operating Runbook"}</DialogTitle>
          </div>
          <DialogDescription>
            Define step-by-step remediation procedures that operators can execute when incidents occur.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="p-3 text-sm rounded-lg bg-destructive/10 text-destructive border border-destructive/20">
            {error}
          </div>
        )}

        <div className="space-y-4 py-2">
          {/* Project & Job */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase text-muted-foreground">Project *</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm ring-offset-background focus:outline-none focus:ring-1 focus:ring-ring"
                value={projectId || ""}
                onChange={(e) => {
                  const pid = Number(e.target.value);
                  setProjectId(pid);
                  setJobId(null);
                }}
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase text-muted-foreground">Target Job (Optional)</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm ring-offset-background focus:outline-none focus:ring-1 focus:ring-ring"
                value={jobId || ""}
                onChange={(e) => setJobId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">All Jobs in Project</option>
                {availableJobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Name */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Runbook Name *</Label>
            <Input
              placeholder="e.g. Worker High Failure Rate Recovery SOP"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          {/* Trigger Type & Active Toggle */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase text-muted-foreground">Incident Trigger Matching</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm ring-offset-background focus:outline-none focus:ring-1 focus:ring-ring"
                value={triggerType}
                onChange={(e) => setTriggerType(e.target.value)}
              >
                {TRIGGER_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center space-x-2 pt-5">
              <Switch id="is-active" checked={isActive} onCheckedChange={setIsActive} />
              <Label htmlFor="is-active" className="text-sm font-medium cursor-pointer">
                Active & Recommended
              </Label>
            </div>
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Description & Context</Label>
            <Textarea
              placeholder="Provide context, links to dashboards, or prerequisite access details…"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="resize-none"
            />
          </div>

          {/* Steps Builder */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold uppercase text-muted-foreground">
                Runbook Steps ({steps.length}) *
              </Label>
              <Button type="button" size="sm" variant="outline" className="h-7 text-xs gap-1" onClick={handleAddStep}>
                <Plus className="h-3 w-3" /> Add Step
              </Button>
            </div>

            <div className="space-y-3">
              {steps.map((step, index) => (
                <div
                  key={step.id || index}
                  className="p-3 rounded-lg border bg-card/60 shadow-xs space-y-2 relative group"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex items-center justify-center h-5 w-5 rounded-full bg-primary/10 text-primary text-xs font-mono font-semibold shrink-0">
                      {index + 1}
                    </span>
                    <Input
                      placeholder={`Step ${index + 1} action title (e.g. Restart worker pod)`}
                      value={step.title}
                      onChange={(e) => handleStepChange(index, "title", e.target.value)}
                      className="h-8 text-sm"
                    />
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0"
                        disabled={index === 0}
                        onClick={() => handleMoveStep(index, "up")}
                      >
                        <ArrowUp className="h-3 w-3" />
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0"
                        disabled={index === steps.length - 1}
                        onClick={() => handleMoveStep(index, "down")}
                      >
                        <ArrowDown className="h-3 w-3" />
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                        disabled={steps.length <= 1}
                        onClick={() => handleRemoveStep(index)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>

                  <Input
                    placeholder="Optional guidance or command to run (e.g. kubectl rollout restart deploy/worker)"
                    value={step.description || ""}
                    onChange={(e) => handleStepChange(index, "description", e.target.value)}
                    className="h-7 text-xs text-muted-foreground"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || !name.trim()}
          >
            {saveMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {runbook ? "Save Changes" : "Create Runbook"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
