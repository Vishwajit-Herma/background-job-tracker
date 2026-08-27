"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { JobExpectation, updateJobExpectation } from "@/lib/api/reliability";
import { Loader2, Settings2 } from "lucide-react";

interface EditExpectationDialogProps {
  jobId: number;
  jobName: string;
  expectation: JobExpectation | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type TimeUnit = "seconds" | "minutes" | "hours";

function toUnitAndVal(totalSeconds: number | null | undefined, defaultUnit: TimeUnit = "minutes"): { val: string; unit: TimeUnit } {
  if (totalSeconds === null || totalSeconds === undefined || totalSeconds === 0) {
    return { val: "", unit: defaultUnit };
  }
  if (totalSeconds >= 3600 && totalSeconds % 3600 === 0) {
    return { val: (totalSeconds / 3600).toString(), unit: "hours" };
  }
  if (totalSeconds >= 60 && totalSeconds % 60 === 0) {
    return { val: (totalSeconds / 60).toString(), unit: "minutes" };
  }
  return { val: totalSeconds.toString(), unit: "seconds" };
}

function toSeconds(val: string, unit: TimeUnit): number | null {
  const trimmed = val.trim();
  if (!trimmed) return null;
  const num = parseFloat(trimmed);
  if (isNaN(num) || num < 0) return null;

  if (unit === "hours") return Math.round(num * 3600);
  if (unit === "minutes") return Math.round(num * 60);
  return Math.round(num);
}

export function EditExpectationDialog({
  jobId,
  jobName,
  expectation,
  open,
  onOpenChange,
}: EditExpectationDialogProps) {
  const queryClient = useQueryClient();

  const [intervalVal, setIntervalVal] = useState("");
  const [intervalUnit, setIntervalUnit] = useState<TimeUnit>("minutes");

  const [graceVal, setGraceVal] = useState("");
  const [graceUnit, setGraceUnit] = useState<TimeUnit>("minutes");

  const [runtimeVal, setRuntimeVal] = useState("");
  const [runtimeUnit, setRuntimeUnit] = useState<TimeUnit>("minutes");

  const [queueDelayVal, setQueueDelayVal] = useState("");
  const [queueDelayUnit, setQueueDelayUnit] = useState<TimeUnit>("seconds");

  const [isEnabled, setIsEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setError(null);
      if (expectation) {
        const i = toUnitAndVal(expectation.expected_interval_seconds, "minutes");
        setIntervalVal(i.val);
        setIntervalUnit(i.unit);

        const g = toUnitAndVal(expectation.grace_period_seconds, "minutes");
        setGraceVal(g.val);
        setGraceUnit(g.unit);

        const r = toUnitAndVal(expectation.max_runtime_seconds, "minutes");
        setRuntimeVal(r.val);
        setRuntimeUnit(r.unit);

        const q = toUnitAndVal(expectation.max_queue_delay_seconds, "seconds");
        setQueueDelayVal(q.val);
        setQueueDelayUnit(q.unit);

        setIsEnabled(expectation.is_enabled);
      } else {
        setIntervalVal("");
        setIntervalUnit("minutes");
        setGraceVal("1");
        setGraceUnit("minutes");
        setRuntimeVal("");
        setRuntimeUnit("minutes");
        setQueueDelayVal("300");
        setQueueDelayUnit("seconds");
        setIsEnabled(true);
      }
    }
  }, [open, expectation]);

  const mutation = useMutation({
    mutationFn: (data: Partial<JobExpectation>) => updateJobExpectation(jobId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job-reliability", jobId] });
      queryClient.invalidateQueries({ queryKey: ["job-expectation", jobId] });
      queryClient.invalidateQueries({ queryKey: ["project-reliability"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["jobs-paginated"] });
      onOpenChange(false);
    },
    onError: (err: any) => {
      const msg = err.message || err.response?.data?.error || err.response?.data?.detail || "Failed to update expectations.";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    },
  });

  const handleSave = () => {
    setError(null);
    const intervalSec = toSeconds(intervalVal, intervalUnit);
    const graceSec = toSeconds(graceVal, graceUnit) ?? 0;
    const runtimeSec = toSeconds(runtimeVal, runtimeUnit);
    const queueDelaySec = toSeconds(queueDelayVal, queueDelayUnit);

    if (intervalSec !== null && intervalSec < 1) {
      setError("Expected interval must be at least 1 second.");
      return;
    }
    if (runtimeSec !== null && runtimeSec < 1) {
      setError("Maximum runtime must be at least 1 second.");
      return;
    }
    if (graceSec < 0) {
      setError("Grace period must be non-negative.");
      return;
    }
    if (queueDelaySec !== null && queueDelaySec < 0) {
      setError("Maximum queue delay must be non-negative.");
      return;
    }

    mutation.mutate({
      expected_interval_seconds: intervalSec,
      grace_period_seconds: graceSec,
      max_runtime_seconds: runtimeSec,
      max_queue_delay_seconds: queueDelaySec,
      is_enabled: isEnabled,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Settings2 className="h-5 w-5 text-primary" /> Edit Reliability Expectations
          </DialogTitle>
          <DialogDescription>
            Configure expected interval, runtime limits, and grace buffers for <span className="font-semibold text-foreground">{jobName}</span>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2 text-sm">
          {error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
              {error}
            </div>
          )}

          {/* Expected Interval */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="font-medium text-foreground">Expected Execution Interval</Label>
              <span className="text-xs text-muted-foreground">Cadence</span>
            </div>
            <div className="flex gap-2">
              <Input
                type="number"
                min="1"
                placeholder="e.g. 5 (leave blank to infer from baseline)"
                value={intervalVal}
                onChange={(e) => setIntervalVal(e.target.value)}
                className="flex-1"
              />
              <Select value={intervalUnit} onValueChange={(u) => setIntervalUnit(u as TimeUnit)}>
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="seconds">Seconds</SelectItem>
                  <SelectItem value="minutes">Minutes</SelectItem>
                  <SelectItem value="hours">Hours</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <p className="text-[11px] text-muted-foreground">
              How often this job is expected to run (e.g. every 5 minutes).
            </p>
          </div>

          {/* Grace Period */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="font-medium text-foreground">Grace Period</Label>
              <span className="text-xs text-muted-foreground">Buffer before alert</span>
            </div>
            <div className="flex gap-2">
              <Input
                type="number"
                min="0"
                placeholder="e.g. 1"
                value={graceVal}
                onChange={(e) => setGraceVal(e.target.value)}
                className="flex-1"
              />
              <Select value={graceUnit} onValueChange={(u) => setGraceUnit(u as TimeUnit)}>
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="seconds">Seconds</SelectItem>
                  <SelectItem value="minutes">Minutes</SelectItem>
                  <SelectItem value="hours">Hours</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Extra buffer added to expected interval before marking a run as missed.
            </p>
          </div>

          {/* Max Runtime */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="font-medium text-foreground">Maximum Allowed Runtime</Label>
              <span className="text-xs text-muted-foreground">Stall detection</span>
            </div>
            <div className="flex gap-2">
              <Input
                type="number"
                min="1"
                placeholder="e.g. 2 (leave blank to infer from baseline)"
                value={runtimeVal}
                onChange={(e) => setRuntimeVal(e.target.value)}
                className="flex-1"
              />
              <Select value={runtimeUnit} onValueChange={(u) => setRuntimeUnit(u as TimeUnit)}>
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="seconds">Seconds</SelectItem>
                  <SelectItem value="minutes">Minutes</SelectItem>
                  <SelectItem value="hours">Hours</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <p className="text-[11px] text-muted-foreground">
              If an execution runs longer than this limit, a STALLED finding is flagged.
            </p>
          </div>

          {/* Max Queue Delay */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="font-medium text-foreground">Maximum Queue Delay</Label>
              <span className="text-xs text-muted-foreground">Queue latency</span>
            </div>
            <div className="flex gap-2">
              <Input
                type="number"
                min="0"
                placeholder="e.g. 300 (5 min)"
                value={queueDelayVal}
                onChange={(e) => setQueueDelayVal(e.target.value)}
                className="flex-1"
              />
              <Select value={queueDelayUnit} onValueChange={(u) => setQueueDelayUnit(u as TimeUnit)}>
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="seconds">Seconds</SelectItem>
                  <SelectItem value="minutes">Minutes</SelectItem>
                  <SelectItem value="hours">Hours</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Flag an OVERDUE finding if a task remains pending in the queue beyond this threshold.
            </p>
          </div>

          {/* Enable / Disable Switch */}
          <div className="pt-2 border-t flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="monitoring-switch" className="font-medium text-foreground cursor-pointer">
                Reliability Monitoring
              </Label>
              <p className="text-xs text-muted-foreground">
                When disabled, reliability checks and finding detections are paused.
              </p>
            </div>
            <Switch
              id="monitoring-switch"
              checked={isEnabled}
              onCheckedChange={setIsEnabled}
            />
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Expectations
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
