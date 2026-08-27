"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { JobReliabilityOverview, ExpectationSource } from "@/lib/api/reliability";
import { formatDurationSeconds } from "@/lib/reliability-utils";
import { EditExpectationDialog } from "./edit-expectation-dialog";
import { Sliders, Pencil, CheckCircle2, ShieldOff, Sparkles, SlidersHorizontal, Clock, Hourglass } from "lucide-react";

interface ExpectationCardProps {
  reliability: JobReliabilityOverview;
  canManage?: boolean;
}

function SourceBadge({ source }: { source: ExpectationSource }) {
  if (source === "CONFIGURED") {
    return (
      <Badge variant="info" className="text-[10px] px-1.5 py-0 h-4">
        Configured
      </Badge>
    );
  }
  if (source === "BASELINE") {
    return (
      <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 flex items-center gap-1 bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/20">
        <Sparkles className="h-2.5 w-2.5" /> Based on baseline
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 text-muted-foreground">
      Not configured
    </Badge>
  );
}

export function ExpectationCard({ reliability, canManage = true }: ExpectationCardProps) {
  const [editOpen, setEditOpen] = useState(false);

  const expectation = reliability.expectation;
  const isEnabled = reliability.is_enabled;

  const intervalSec = reliability.expected_interval_seconds;
  const graceSec = reliability.grace_period_seconds;
  const runtimeSec = reliability.max_runtime_seconds;
  const queueDelaySec = expectation?.max_queue_delay_seconds ?? null;

  return (
    <>
      <Card className="shadow-sm border-border/80 h-full flex flex-col justify-between">
        <CardHeader className="pb-3 border-b bg-muted/20">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-primary" /> Execution Expectations
            </CardTitle>
            {canManage && (
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5 shadow-none"
                onClick={() => setEditOpen(true)}
              >
                <Pencil className="h-3 w-3" /> Edit
              </Button>
            )}
          </div>
        </CardHeader>

        <CardContent className="pt-4 space-y-3.5 flex-1">
          {/* Expected Interval Row */}
          <div className="flex items-center justify-between text-sm py-1 border-b border-border/50">
            <div className="space-y-0.5">
              <span className="font-medium text-foreground flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-muted-foreground" /> Expected Interval
              </span>
              <p className="text-[11px] text-muted-foreground">Cadence between scheduled runs</p>
            </div>
            <div className="text-right flex flex-col items-end gap-1">
              <span className="font-semibold text-foreground">
                {intervalSec ? `Every ${formatDurationSeconds(intervalSec)}` : "—"}
              </span>
              <SourceBadge source={reliability.expectation_source} />
            </div>
          </div>

          {/* Grace Period Row */}
          <div className="flex items-center justify-between text-sm py-1 border-b border-border/50">
            <div className="space-y-0.5">
              <span className="font-medium text-foreground flex items-center gap-1.5">
                <Hourglass className="h-3.5 w-3.5 text-muted-foreground" /> Grace Period
              </span>
              <p className="text-[11px] text-muted-foreground">Buffer before flagging missed run</p>
            </div>
            <div className="text-right">
              <span className="font-semibold text-foreground">
                {graceSec > 0 ? formatDurationSeconds(graceSec) : "0 sec (Strict)"}
              </span>
            </div>
          </div>

          {/* Max Runtime Row */}
          <div className="flex items-center justify-between text-sm py-1 border-b border-border/50">
            <div className="space-y-0.5">
              <span className="font-medium text-foreground flex items-center gap-1.5">
                <Sliders className="h-3.5 w-3.5 text-muted-foreground" /> Maximum Runtime
              </span>
              <p className="text-[11px] text-muted-foreground">Threshold for stalled executions</p>
            </div>
            <div className="text-right flex flex-col items-end gap-1">
              <span className="font-semibold text-foreground">
                {runtimeSec ? formatDurationSeconds(runtimeSec) : "—"}
              </span>
              <SourceBadge
                source={
                  expectation?.max_runtime_seconds
                    ? "CONFIGURED"
                    : reliability.baseline?.is_sufficient
                    ? "BASELINE"
                    : "NONE"
                }
              />
            </div>
          </div>

          {/* Max Queue Delay Row */}
          <div className="flex items-center justify-between text-sm py-1 border-b border-border/50">
            <div className="space-y-0.5">
              <span className="font-medium text-foreground flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-muted-foreground" /> Maximum Queue Delay
              </span>
              <p className="text-[11px] text-muted-foreground">Limit before flagging overdue queue</p>
            </div>
            <div className="text-right">
              <span className="font-semibold text-foreground">
                {queueDelaySec !== null ? formatDurationSeconds(queueDelaySec) : "Not configured"}
              </span>
            </div>
          </div>

          {/* Monitoring State */}
          <div className="flex items-center justify-between text-sm pt-1">
            <span className="font-medium text-foreground">Monitoring State</span>
            <div>
              {isEnabled ? (
                <Badge variant="success" className="text-[10px] px-2 py-0.5 gap-1">
                  <CheckCircle2 className="h-3 w-3" /> Enabled
                </Badge>
              ) : (
                <Badge variant="secondary" className="text-[10px] px-2 py-0.5 gap-1 text-muted-foreground">
                  <ShieldOff className="h-3 w-3" /> Disabled
                </Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <EditExpectationDialog
        jobId={reliability.job_id}
        jobName={reliability.job_name}
        expectation={expectation}
        open={editOpen}
        onOpenChange={setEditOpen}
      />
    </>
  );
}
