"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertMetricType, AlertRule, createAlertRule, updateAlertRule } from "@/lib/api/alerts";
import { useWorkspace } from "@/hooks/use-workspace";
import axios from "axios";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Activity, Clock, Loader2, ShieldAlert, Sparkles, Zap } from "lucide-react";

interface MetricInfo {
  category: "Standard Metric" | "Reliability SLA" | "Intelligent Anomaly";
  title: string;
  badge: string;
  badgeColorClass: string;
  unit: string;
  isAnomaly: boolean;
  isSla: boolean;
  description: string;
  howItWorks: string;
  example: string;
}

const METRIC_DEFINITIONS: Record<AlertMetricType, MetricInfo> = {
  FAILURE_RATE: {
    category: "Standard Metric",
    title: "Failure Rate",
    badge: "Fixed Threshold",
    badgeColorClass: "bg-destructive/10 text-destructive border-destructive/20",
    unit: "%",
    isAnomaly: false,
    isSla: false,
    description: "Monitors the percentage of failed executions over a rolling time window.",
    howItWorks: "Triggers when (failed executions ÷ total executions) × 100 exceeds the threshold within the configured window.",
    example: "e.g., Threshold 10% over 60m triggers if more than 10% of jobs fail in the last hour.",
  },
  RETRY_RATE: {
    category: "Standard Metric",
    title: "Retry Rate",
    badge: "Fixed Threshold",
    badgeColorClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    unit: "%",
    isAnomaly: false,
    isSla: false,
    description: "Monitors the percentage of executions that required one or more retry attempts.",
    howItWorks: "Triggers when (retried executions ÷ total executions) × 100 exceeds the threshold within the window.",
    example: "e.g., Threshold 20% over 30m flags transient downstream instability before complete failure occurs.",
  },
  P95_DURATION: {
    category: "Standard Metric",
    title: "P95 Duration",
    badge: "Fixed Threshold",
    badgeColorClass: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
    unit: "ms",
    isAnomaly: false,
    isSla: false,
    description: "Monitors the 95th percentile execution duration for runtime bottlenecks and slowdowns.",
    howItWorks: "Calculates the 95th percentile duration of completed runs. Triggers when P95 duration exceeds threshold in milliseconds.",
    example: "e.g., Threshold 5000ms triggers if the slowest 5% of runs take longer than 5.0 seconds.",
  },
  MISSED_EXECUTION: {
    category: "Reliability SLA",
    title: "Missed Execution",
    badge: "Cadence SLA",
    badgeColorClass: "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20",
    unit: "seconds",
    isAnomaly: false,
    isSla: true,
    description: "Detects when a periodic or scheduled background job fails to run on its expected cadence.",
    howItWorks: "Evaluates expected interval + grace period. Triggers if no new execution occurs before the expected deadline.",
    example: "e.g., An hourly cron job with a 5m grace period triggers an incident if 65 minutes pass without an execution.",
  },
  STALLED_EXECUTION: {
    category: "Reliability SLA",
    title: "Stalled Execution",
    badge: "Runtime SLA",
    badgeColorClass: "bg-destructive/10 text-destructive border-destructive/20",
    unit: "seconds",
    isAnomaly: false,
    isSla: true,
    description: "Detects background tasks that are currently executing but have exceeded their maximum allowed runtime limit.",
    howItWorks: "Inspects currently running executions. Triggers when elapsed execution time exceeds configured max runtime.",
    example: "e.g., A task with a 60s runtime limit running for 10 minutes is flagged as stalled (zombie or stuck worker).",
  },
  OVERDUE_EXECUTION: {
    category: "Reliability SLA",
    title: "Overdue Execution",
    badge: "Queue Delay SLA",
    badgeColorClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    unit: "seconds",
    isAnomaly: false,
    isSla: true,
    description: "Detects queued tasks that have remained pending/waiting for a worker longer than allowed.",
    howItWorks: "Triggers when a task's queue delay (time spent waiting in Redis/RabbitMQ before a worker starts processing) exceeds the threshold.",
    example: "e.g., Worker pool starvation causing tasks to sit pending for > 5 minutes.",
  },
  FAILURE_RATE_ANOMALY: {
    category: "Intelligent Anomaly",
    title: "Failure Rate Anomaly",
    badge: "Statistical Baseline",
    badgeColorClass: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20",
    unit: "ratio",
    isAnomaly: true,
    isSla: false,
    description: "Statistical detector that compares current 60-minute failure rate against the job's 7-day historical baseline.",
    howItWorks: "Triggers automatically when current 60m failure rate is ≥ 3× normal baseline (with a min 5.0% absolute increase). Adapts dynamically if baseline changes.",
    example: "e.g., If normal baseline is 1.0% and failure rate surges to 8.0%, this triggers an incident automatically without manual threshold tuning.",
  },
  RETRY_RATE_ANOMALY: {
    category: "Intelligent Anomaly",
    title: "Retry Rate Anomaly",
    badge: "Statistical Baseline",
    badgeColorClass: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20",
    unit: "ratio",
    isAnomaly: true,
    isSla: false,
    description: "Statistical detector that compares current 60-minute retry rate against the 7-day historical baseline.",
    howItWorks: "Triggers automatically when current 60m retry rate is ≥ 3× normal baseline (with a min 5.0% absolute increase).",
    example: "e.g., Detects when third-party APIs (Stripe, Sendgrid) start throwing transient errors causing unusual retry bursts.",
  },
  DURATION_ANOMALY: {
    category: "Intelligent Anomaly",
    title: "Duration Anomaly",
    badge: "Statistical Baseline",
    badgeColorClass: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20",
    unit: "ratio",
    isAnomaly: true,
    isSla: false,
    description: "Statistical detector that compares current 60-minute P95 runtime against the 7-day historical baseline.",
    howItWorks: "Triggers automatically when current 60m P95 duration is ≥ 2.5× normal baseline (with a min 1,000ms increase).",
    example: "e.g., Catches slow database queries or network latency degrading job performance from 200ms to 2.5s.",
  },
  EXECUTION_VOLUME_ANOMALY: {
    category: "Intelligent Anomaly",
    title: "Execution Volume Anomaly",
    badge: "Statistical Baseline",
    badgeColorClass: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20",
    unit: "ratio",
    isAnomaly: true,
    isSla: false,
    description: "Statistical detector that compares current 60-minute execution volume with the historical average hourly volume (global average across sample window, not seasonality-aware).",
    howItWorks: "Triggers on volume surge (≥ 4.0× historical hourly avg) or sudden drop (≤ 0.2× historical hourly avg) for jobs with at least 5 runs/hr.",
    example: "e.g., Catches runaway loop enqueues (surge) or upstream producer/webhook crashes (drop).",
  },
};

const formSchema = z.object({
  project: z.coerce.number().min(1, "Project is required"),
  job: z.coerce.number().optional().nullable(),
  metric: z.enum([
    "FAILURE_RATE",
    "RETRY_RATE",
    "P95_DURATION",
    "MISSED_EXECUTION",
    "STALLED_EXECUTION",
    "OVERDUE_EXECUTION",
    "FAILURE_RATE_ANOMALY",
    "RETRY_RATE_ANOMALY",
    "DURATION_ANOMALY",
    "EXECUTION_VOLUME_ANOMALY",
  ]),
  threshold: z.coerce.number().min(0, "Threshold must be positive"),
  window_minutes: z.coerce.number().min(1, "Minimum 1 minute").max(1440, "Maximum 24 hours (1440 mins)"),
  severity: z.enum(["DEGRADED", "CRITICAL"]),
  is_active: z.boolean(),
});

type FormValues = {
  project: number;
  job?: number | null;
  metric: AlertMetricType;
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
  const selectedMetric = watch("metric") || "FAILURE_RATE";
  const selectedSeverity = watch("severity");
  const isActive = watch("is_active");

  const metricInfo = METRIC_DEFINITIONS[selectedMetric] || METRIC_DEFINITIONS.FAILURE_RATE;

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
          window_minutes: ruleToEdit.window_minutes || 60,
          severity: ruleToEdit.severity,
          is_active: ruleToEdit.is_active,
        });
      } else {
        const defaultProject = projects.length > 0 ? projects[0].id : undefined;
        reset({
          project: defaultProject as unknown as number,
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

  useEffect(() => {
    if (open && selectedProjectId && projects.length > 0) {
      if (!projects.some((p) => p.id === selectedProjectId)) {
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
        threshold: metricInfo.isAnomaly ? 0 : Number(values.threshold) || 0,
        window_minutes: metricInfo.isAnomaly ? 60 : Number(values.window_minutes) || 60,
        job: values.job ? Number(values.job) : null,
      };

      if (isEditing && ruleToEdit) {
        await updateAlertRule(ruleToEdit.id, payload);
      } else {
        await createAlertRule(payload);
      }

      await queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
      onOpenChange(false);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        const errorMsg =
          err.response?.data?.message ||
          (typeof err.response?.data?.errors === "object"
            ? Object.values(err.response.data.errors).flat().join(", ")
            : err.message);
        setServerError(errorMsg || "Failed to save alert rule. Please check your inputs.");
      } else {
        setServerError("An unexpected error occurred while saving the alert rule.");
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[620px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">
            {isEditing ? "Edit Alert Rule" : "Create Alert Rule"}
          </DialogTitle>
          <DialogDescription className="text-sm">
            Configure automated incident escalation rules when background jobs degrade or fail.
          </DialogDescription>
        </DialogHeader>

        {serverError && (
          <div className="flex items-center gap-2 p-3 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span>{serverError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-1">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="project">Project</Label>
              <Select
                value={selectedProjectId ? selectedProjectId.toString() : ""}
                onValueChange={(val) => {
                  if (val) {
                    setValue("project", Number(val), { shouldValidate: true });
                    setValue("job", null);
                  }
                }}
                disabled={isEditing || projects.length === 0}
              >
                <SelectTrigger id="project" className="w-full">
                  <SelectValue placeholder={projects.length === 0 ? "No authorized projects" : "Select project"}>
                    {selectedProjectId ? projects.find((p) => p.id === selectedProjectId)?.name : ""}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={p.id.toString()}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.project && (
                <p className="text-xs text-destructive">{errors.project.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="job">Target Job (Optional)</Label>
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
                <SelectTrigger id="job" className="w-full">
                  <SelectValue placeholder="All jobs (Project-level)">
                    {selectedJobId && selectedJobId !== 0
                      ? availableJobs.find((j) => j.id === selectedJobId)?.name
                      : "All jobs (Project-level)"}
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

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="metric">Metric to Monitor</Label>
              <span className="text-[11px] text-muted-foreground">
                {metricInfo.category}
              </span>
            </div>

            <Select
              value={selectedMetric}
              onValueChange={(val) => {
                if (val) {
                  const metricVal = val as AlertMetricType;
                  setValue("metric", metricVal, { shouldValidate: true });
                  if (METRIC_DEFINITIONS[metricVal]?.isAnomaly) {
                    setValue("threshold", 0);
                    setValue("window_minutes", 60);
                  }
                }
              }}
            >
              <SelectTrigger id="metric" className="w-full">
                <SelectValue placeholder="Select metric" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel className="text-xs font-semibold text-foreground/80 flex items-center gap-1.5 pt-1">
                    <Activity className="h-3.5 w-3.5 text-primary" /> Standard Metrics (Fixed Limits)
                  </SelectLabel>
                  <SelectItem value="FAILURE_RATE">Failure Rate (%)</SelectItem>
                  <SelectItem value="RETRY_RATE">Retry Rate (%)</SelectItem>
                  <SelectItem value="P95_DURATION">P95 Duration (ms)</SelectItem>
                </SelectGroup>
                <SelectGroup>
                  <SelectLabel className="text-xs font-semibold text-foreground/80 flex items-center gap-1.5 pt-2">
                    <Clock className="h-3.5 w-3.5 text-orange-500" /> Reliability & SLAs
                  </SelectLabel>
                  <SelectItem value="MISSED_EXECUTION">Missed Execution (Cadence SLA)</SelectItem>
                  <SelectItem value="STALLED_EXECUTION">Stalled Execution (Runtime SLA)</SelectItem>
                  <SelectItem value="OVERDUE_EXECUTION">Overdue Execution (Queue Delay SLA)</SelectItem>
                </SelectGroup>
                <SelectGroup>
                  <SelectLabel className="text-xs font-semibold text-purple-700 dark:text-purple-400 flex items-center gap-1.5 pt-2">
                    <Zap className="h-3.5 w-3.5" /> Intelligent Anomaly Detection
                  </SelectLabel>
                  <SelectItem value="FAILURE_RATE_ANOMALY">Failure Rate Anomaly (≥ 3× Baseline)</SelectItem>
                  <SelectItem value="RETRY_RATE_ANOMALY">Retry Rate Anomaly (≥ 3× Baseline)</SelectItem>
                  <SelectItem value="DURATION_ANOMALY">Duration Anomaly (≥ 2.5× Baseline)</SelectItem>
                  <SelectItem value="EXECUTION_VOLUME_ANOMALY">Execution Volume Anomaly (Surge/Drop)</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            {errors.metric && (
              <p className="text-xs text-destructive">{errors.metric.message}</p>
            )}
          </div>

          <div className="rounded-lg border bg-muted/30 p-3.5 text-xs space-y-2">
            <div className="flex items-center justify-between">
              <div className="font-semibold text-foreground flex items-center gap-1.5">
                {metricInfo.isAnomaly ? (
                  <Zap className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                ) : metricInfo.isSla ? (
                  <Clock className="h-4 w-4 text-orange-500" />
                ) : (
                  <Activity className="h-4 w-4 text-primary" />
                )}
                {metricInfo.title}
              </div>
              <Badge variant="outline" className={`text-[10px] py-0 px-2 font-medium ${metricInfo.badgeColorClass}`}>
                {metricInfo.badge}
              </Badge>
            </div>
            <p className="text-muted-foreground leading-relaxed">
              {metricInfo.description}
            </p>
            <div className="pt-1 border-t border-border/60 space-y-1 text-[11px]">
              <p className="text-foreground/90 font-medium">
                <span className="text-muted-foreground font-normal">Trigger condition: </span>
                {metricInfo.howItWorks}
              </p>
              <p className="text-muted-foreground italic">
                {metricInfo.example}
              </p>
            </div>
          </div>

          {metricInfo.isAnomaly ? (
            <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-3 text-xs space-y-1">
              <div className="flex items-center gap-1.5 font-semibold text-purple-900 dark:text-purple-300">
                <Sparkles className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400" />
                Adaptive Baseline Auto-Tuning Active
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                This rule uses your job's <strong>7-day statistical baseline</strong>. No manual threshold configuration is needed.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="threshold">
                  {metricInfo.isSla ? "Extra Grace Buffer (seconds, optional)" : "Threshold"}
                </Label>
                <Input id="threshold" type="number" step="0.1" {...register("threshold", { valueAsNumber: true })} />
                {errors.threshold && <p className="text-xs text-destructive">{errors.threshold.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="window_minutes">Rolling Window (Minutes)</Label>
                <Input id="window_minutes" type="number" {...register("window_minutes", { valueAsNumber: true })} />
                {errors.window_minutes && <p className="text-xs text-destructive">{errors.window_minutes.message}</p>}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <div className="space-y-1.5">
              <Label htmlFor="severity">Incident Severity</Label>
              <Select value={selectedSeverity} onValueChange={(val) => setValue("severity", val as any, { shouldValidate: true })}>
                <SelectTrigger id="severity"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="CRITICAL">Critical (Immediate Escalation)</SelectItem>
                  <SelectItem value="DEGRADED">Degraded (Warning / High Latency)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-3 shadow-sm">
              <div className="space-y-0.5">
                <Label className="text-sm font-medium">Active Rule</Label>
                <p className="text-[11px] text-muted-foreground">Disabled rules won't trigger.</p>
              </div>
              <Switch checked={isActive} onCheckedChange={(checked) => setValue("is_active", checked)} />
            </div>
          </div>

          <DialogFooter className="pt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
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
