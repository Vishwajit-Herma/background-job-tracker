"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { JobBaseline, recalculateJobBaseline } from "@/lib/api/reliability";
import { formatDurationMs, formatDurationSeconds, formatReliabilityTime } from "@/lib/reliability-utils";
import { BarChart3, RotateCw, Sparkles, AlertCircle, CheckCircle2, ChevronDown, ChevronUp, Clock, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

interface BaselineCardProps {
  jobId: number;
  baseline: JobBaseline | null;
  canManage?: boolean;
}

export function BaselineCard({ jobId, baseline, canManage = true }: BaselineCardProps) {
  const queryClient = useQueryClient();
  const [sampleWindow, setSampleWindow] = useState("7");
  const [showSecondary, setShowSecondary] = useState(false);
  const [queuedMessage, setQueuedMessage] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => recalculateJobBaseline(jobId, { sample_window_days: parseInt(sampleWindow, 10) }),
    onSuccess: (res) => {
      setQueuedMessage(res.message || `Baseline recalculation queued over a ${sampleWindow}-day window.`);
      queryClient.invalidateQueries({ queryKey: ["job-reliability", jobId] });
      queryClient.invalidateQueries({ queryKey: ["project-reliability"] });
      setTimeout(() => setQueuedMessage(null), 6000);
    },
    onError: (err: any) => {
      alert(err.message || "Failed to trigger baseline recalculation.");
    },
  });

  const isSufficient = baseline?.is_sufficient ?? false;
  const totalAnalyzed = baseline?.total_executions_analyzed ?? 0;
  const calcTime = formatReliabilityTime(baseline?.calculated_at);

  return (
    <Card className="shadow-sm border-border/80">
      <CardHeader className="pb-3 border-b bg-muted/20">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" /> Statistical Baseline
            </CardTitle>
            {isSufficient ? (
              <Badge variant="success" className="text-[10px] px-2 py-0.5 gap-1">
                <Sparkles className="h-2.5 w-2.5" /> Sufficient History
              </Badge>
            ) : (
              <Badge variant="secondary" className="text-[10px] px-2 py-0.5 gap-1 text-muted-foreground">
                <AlertCircle className="h-2.5 w-2.5" /> Establishing
              </Badge>
            )}
          </div>

          {/* Recalculate Controls */}
          {canManage && (
            <div className="flex items-center gap-2">
              <Select value={sampleWindow} onValueChange={(val) => { if (val) setSampleWindow(val); }} disabled={mutation.isPending}>
                <SelectTrigger className="h-8 w-28 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7">7 days</SelectItem>
                  <SelectItem value="14">14 days</SelectItem>
                  <SelectItem value="30">30 days</SelectItem>
                  <SelectItem value="90">90 days</SelectItem>
                </SelectContent>
              </Select>

              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5 shadow-none"
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending}
              >
                <RotateCw className={cn("h-3 w-3", mutation.isPending && "animate-spin")} />
                {mutation.isPending ? "Queuing..." : "Recalculate"}
              </Button>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="pt-4 space-y-4">
        {queuedMessage && (
          <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 flex items-center gap-2 text-xs text-primary animate-fadeIn">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{queuedMessage} TanStack query will automatically refresh when completed.</span>
          </div>
        )}

        {!isSufficient ? (
          <div className="rounded-xl border border-dashed p-6 text-center space-y-2 bg-muted/10">
            <BarChart3 className="h-8 w-8 mx-auto text-muted-foreground/40" />
            <h4 className="text-sm font-semibold text-foreground">Baseline not established yet</h4>
            <p className="text-xs text-muted-foreground max-w-md mx-auto">
              Only <span className="font-semibold text-foreground">{totalAnalyzed}</span> execution
              {totalAnalyzed === 1 ? "" : "s"} recorded in the current sample window. At least 3 executions and 2
              consecutive intervals are required to derive statistical cadences and runtime percentiles.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Primary KPI Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              <div className="p-3 rounded-lg border bg-card/60">
                <div className="flex items-center gap-1 text-[11px] text-muted-foreground mb-1">
                  <Zap className="h-3 w-3" /> Samples Analyzed
                </div>
                <p className="text-lg font-bold text-foreground">
                  {totalAnalyzed.toLocaleString()} <span className="text-xs font-normal text-muted-foreground">runs</span>
                </p>
                <p className="text-[10px] text-muted-foreground">{baseline?.sample_window_days}d sample window</p>
              </div>

              <div className="p-3 rounded-lg border bg-card/60">
                <div className="flex items-center gap-1 text-[11px] text-muted-foreground mb-1">
                  <Clock className="h-3 w-3" /> Median Interval
                </div>
                <p className="text-lg font-bold text-foreground">
                  {formatDurationSeconds(baseline?.median_interval_seconds ? Math.round(baseline.median_interval_seconds) : null)}
                </p>
                <p className="text-[10px] text-muted-foreground">Cadence</p>
              </div>

              <div className="p-3 rounded-lg border bg-card/60">
                <div className="flex items-center gap-1 text-[11px] text-muted-foreground mb-1">
                  Average Runtime
                </div>
                <p className="text-lg font-bold text-foreground">
                  {formatDurationMs(baseline?.avg_runtime_ms)}
                </p>
                <p className="text-[10px] text-muted-foreground">Mean duration</p>
              </div>

              <div className="p-3 rounded-lg border bg-card/60">
                <div className="flex items-center gap-1 text-[11px] text-muted-foreground mb-1">
                  P50 (Median)
                </div>
                <p className="text-lg font-bold text-foreground">
                  {formatDurationMs(baseline?.p50_runtime_ms)}
                </p>
                <p className="text-[10px] text-muted-foreground">50th percentile</p>
              </div>

              <div className="p-3 rounded-lg border bg-card/60">
                <div className="flex items-center gap-1 text-[11px] text-muted-foreground mb-1">
                  P95 Runtime
                </div>
                <p className="text-lg font-bold text-foreground">
                  {formatDurationMs(baseline?.p95_runtime_ms)}
                </p>
                <p className="text-[10px] text-muted-foreground">95th percentile</p>
              </div>

              <div className="p-3 rounded-lg border bg-card/60">
                <div className="flex items-center gap-1 text-[11px] text-muted-foreground mb-1">
                  P99 Runtime
                </div>
                <p className="text-lg font-bold text-foreground">
                  {formatDurationMs(baseline?.p99_runtime_ms)}
                </p>
                <p className="text-[10px] text-muted-foreground">99th percentile</p>
              </div>
            </div>

            {/* Secondary Metrics Collapse */}
            <div className="border-t pt-2">
              <button
                type="button"
                onClick={() => setShowSecondary(!showSecondary)}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-medium transition-colors"
              >
                {showSecondary ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                {showSecondary ? "Hide secondary baseline metrics" : "Show detailed interval statistics"}
              </button>

              {showSecondary && (
                <div className="grid grid-cols-3 gap-3 mt-3 pt-2 border-t border-dashed animate-fadeIn text-xs">
                  <div className="p-2.5 rounded border bg-muted/20">
                    <span className="text-muted-foreground block mb-0.5">Average Interval</span>
                    <span className="font-semibold text-foreground">
                      {formatDurationSeconds(baseline?.avg_interval_seconds ? Math.round(baseline.avg_interval_seconds) : null)}
                    </span>
                  </div>
                  <div className="p-2.5 rounded border bg-muted/20">
                    <span className="text-muted-foreground block mb-0.5">Min Interval</span>
                    <span className="font-semibold text-foreground">
                      {formatDurationSeconds(baseline?.min_interval_seconds ? Math.round(baseline.min_interval_seconds) : null)}
                    </span>
                  </div>
                  <div className="p-2.5 rounded border bg-muted/20">
                    <span className="text-muted-foreground block mb-0.5">Max Interval</span>
                    <span className="font-semibold text-foreground">
                      {formatDurationSeconds(baseline?.max_interval_seconds ? Math.round(baseline.max_interval_seconds) : null)}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Footer Calculation Time */}
            <div className="flex items-center justify-between text-xs text-muted-foreground pt-1 border-t">
              <span>Statistical baseline automatically derived from execution telemetry.</span>
              <span>Calculated {calcTime.relative}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
