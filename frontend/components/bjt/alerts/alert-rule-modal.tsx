"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertRule, createAlertRule, updateAlertRule } from "@/lib/api/alerts";
import { useWorkspace } from "@/hooks/use-workspace";
import { ApiError } from "@/lib/api/client";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Loader2, ShieldAlert } from "lucide-react";

const formSchema = z.object({
  project: z.coerce.number().min(1, "Project is required"),
  job: z.coerce.number().optional().nullable(),
  metric: z.enum(["FAILURE_RATE", "RETRY_RATE", "P95_DURATION"]),
  threshold: z.coerce.number().min(0, "Threshold must be positive"),
  window_minutes: z.coerce.number().min(1, "Minimum 1 minute").max(1440, "Maximum 24 hours (1440 mins)"),
  severity: z.enum(["DEGRADED", "CRITICAL"]),
  is_active: z.boolean(),
});

type FormValues = {
  project: number;
  job?: number | null;
  metric: "FAILURE_RATE" | "RETRY_RATE" | "P95_DURATION";
  threshold: number;
  window_minutes: number;
  severity: "DEGRADED" | "CRITICAL";
  is_active: boolean;
};

interface AlertRuleModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ruleToEdit?: AlertRule | null;
}

export function AlertRuleModal({ open, onOpenChange, ruleToEdit }: AlertRuleModalProps) {
  const queryClient = useQueryClient();
  const isEditing = !!ruleToEdit;
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      project: 0,
      job: null,
      metric: "FAILURE_RATE",
      threshold: 10,
      window_minutes: 60,
      severity: "CRITICAL",
      is_active: true,
    },
  });

  const selectedProjectId = watch("project");
  const selectedJobId = watch("job");
  const selectedMetric = watch("metric");
  const selectedSeverity = watch("severity");
  const isActive = watch("is_active");

  const { projects: rawProjects, jobs, canManageProject } = useWorkspace();

  const projects = rawProjects.filter((p) => canManageProject(p.id));
  const availableJobs = jobs.filter((j) => j.project === selectedProjectId);

  useEffect(() => {
    if (open) {
      setServerError(null);
      if (ruleToEdit) {
        reset({
          project: ruleToEdit.project,
          job: ruleToEdit.job || null,
          metric: ruleToEdit.metric,
          threshold: ruleToEdit.threshold,
          window_minutes: ruleToEdit.window_minutes,
          severity: ruleToEdit.severity,
          is_active: ruleToEdit.is_active,
        });
      } else {
        const defaultProject = projects.length > 0 ? projects[0].id : undefined;
        reset({
          project: defaultProject as unknown as number, // Let react-hook-form handle undefined for empty state
          job: null,
          metric: "FAILURE_RATE",
          threshold: 10,
          window_minutes: 60,
          severity: "CRITICAL",
          is_active: true,
        });
      }
    }
  }, [open, ruleToEdit, reset, projects.length]);

  // Handle case where selected project disappears (e.g. lost permissions)
  useEffect(() => {
    if (open && selectedProjectId && projects.length > 0) {
      if (!projects.some(p => p.id === selectedProjectId)) {
        setValue("project", projects[0].id, { shouldValidate: true });
        setValue("job", null);
      }
    }
  }, [open, selectedProjectId, projects, setValue]);

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      const payload = {
        ...values,
        job: values.job ? Number(values.job) : null,
      };

      if (isEditing && ruleToEdit) {
        await updateAlertRule(ruleToEdit.id, payload);
      } else {
        await createAlertRule(payload);
      }

      queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
      onOpenChange(false);
    } catch (e: any) {
      const err = e as ApiError;
      setServerError(err.message || "Failed to save alert rule. Please check input.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit Alert Rule" : "Create Alert Rule"}</DialogTitle>
          <DialogDescription>
            Configure thresholds to trigger incidents when background jobs fail or degrade in performance.
          </DialogDescription>
        </DialogHeader>

        {serverError && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/15 p-3 text-sm text-destructive">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span>{serverError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="project">Project</Label>
              <Select
                value={
                  selectedProjectId && projects.some((p) => p.id === selectedProjectId)
                    ? selectedProjectId.toString()
                    : ""
                }
                onValueChange={(val) => {
                  if (val) {
                    setValue("project", Number(val), { shouldValidate: true });
                    setValue("job", null);
                  }
                }}
                disabled={isEditing || projects.length === 0}
              >
                <SelectTrigger id="project">
                  <SelectValue placeholder={projects.length === 0 ? "No authorized projects" : "Select project"}>
                    {selectedProjectId ? projects.find(p => p.id === selectedProjectId)?.name : ""}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {projects.length === 0 ? (
                    <SelectItem value="none" disabled className="hidden">
                      No projects
                    </SelectItem>
                  ) : (
                    projects.map((p) => (
                      <SelectItem key={p.id} value={p.id.toString()}>
                        {p.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              {errors.project && (
                <p className="text-xs text-destructive">{errors.project.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="job">Job (Optional)</Label>
              <Select
                value={
                  selectedJobId && availableJobs.some((j) => j.id === selectedJobId)
                    ? selectedJobId.toString()
                    : "0"
                }
                onValueChange={(val) => {
                  if (val) {
                    const num = Number(val);
                    setValue("job", num === 0 ? null : num, { shouldValidate: true });
                  }
                }}
                disabled={!selectedProjectId || isEditing || availableJobs.length === 0}
              >
                <SelectTrigger id="job">
                  <SelectValue placeholder="All jobs (Project-level)">
                    {selectedJobId && selectedJobId !== 0 ? availableJobs.find(j => j.id === selectedJobId)?.name : "All jobs (Project-level)"}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">All jobs (Project-level)</SelectItem>
                  {availableJobs.map((j) => (
                    <SelectItem key={j.id} value={j.id.toString()}>
                      {j.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.job && (
                <p className="text-xs text-destructive">{errors.job.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="metric">Metric</Label>
              <Select
                value={selectedMetric}
                onValueChange={(val) => {
                  if (val) {
                    setValue("metric", val as any, { shouldValidate: true });
                  }
                }}
              >
                <SelectTrigger id="metric">
                  <SelectValue placeholder="Select metric" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="FAILURE_RATE">Failure Rate</SelectItem>
                  <SelectItem value="RETRY_RATE">Retry Rate</SelectItem>
                  <SelectItem value="P95_DURATION">P95 Duration</SelectItem>
                </SelectContent>
              </Select>
              {errors.metric && (
                <p className="text-xs text-destructive">{errors.metric.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="threshold">
                Threshold {selectedMetric?.includes("RATE") ? "(%)" : "(ms)"}
              </Label>
              <Input
                id="threshold"
                type="number"
                step="0.1"
                {...register("threshold", { valueAsNumber: true })}
              />
              {errors.threshold && (
                <p className="text-xs text-destructive">{errors.threshold.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="window_minutes">Window (Minutes)</Label>
              <Input
                id="window_minutes"
                type="number"
                {...register("window_minutes", { valueAsNumber: true })}
              />
              {errors.window_minutes && (
                <p className="text-xs text-destructive">{errors.window_minutes.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="severity">Severity</Label>
              <Select
                value={selectedSeverity}
                onValueChange={(val) => {
                  if (val) {
                    setValue("severity", val as any, { shouldValidate: true });
                  }
                }}
              >
                <SelectTrigger id="severity">
                  <SelectValue placeholder="Select severity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CRITICAL">Critical</SelectItem>
                  <SelectItem value="DEGRADED">Degraded</SelectItem>
                </SelectContent>
              </Select>
              {errors.severity && (
                <p className="text-xs text-destructive">{errors.severity.message}</p>
              )}
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3 shadow-sm mt-4">
            <div className="space-y-0.5">
              <Label className="text-sm font-medium">Active Rule</Label>
              <p className="text-xs text-muted-foreground">
                Disabled rules will not trigger any incidents.
              </p>
            </div>
            <Switch
              checked={isActive}
              onCheckedChange={(checked) => setValue("is_active", checked)}
            />
          </div>

          <DialogFooter className="pt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? "Save Changes" : "Create Rule"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
