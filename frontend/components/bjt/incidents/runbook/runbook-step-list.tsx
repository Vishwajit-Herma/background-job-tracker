"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RunbookStep, RunbookExecution, StepState } from "@/lib/api/incidents";
import { CheckCircle2, Circle, SkipForward, Loader2, Play, User, Clock } from "lucide-react";

interface RunbookStepListProps {
  steps: RunbookStep[];
  execution: RunbookExecution;
  onTransition: (stepId: string, fromState: StepState, toState: StepState) => void;
  isPending: boolean;
}

const STEP_TRANSITIONS: Record<StepState, StepState[]> = {
  PENDING: ["IN_PROGRESS", "SKIPPED"],
  IN_PROGRESS: ["COMPLETED", "SKIPPED"],
  COMPLETED: [],
  SKIPPED: [],
};

function getStepIcon(state: StepState) {
  switch (state) {
    case "COMPLETED":
      return <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />;
    case "IN_PROGRESS":
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin shrink-0" />;
    case "SKIPPED":
      return <SkipForward className="h-4 w-4 text-muted-foreground shrink-0" />;
    default:
      return <Circle className="h-4 w-4 text-muted-foreground shrink-0" />;
  }
}

function getStepBadge(state: StepState) {
  switch (state) {
    case "COMPLETED":
      return (
        <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-[10px] px-1.5 py-0">
          Done
        </Badge>
      );
    case "IN_PROGRESS":
      return (
        <Badge className="bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20 text-[10px] px-1.5 py-0">
          In Progress
        </Badge>
      );
    case "SKIPPED":
      return (
        <Badge variant="outline" className="text-muted-foreground text-[10px] px-1.5 py-0">
          Skipped
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="text-muted-foreground text-[10px] px-1.5 py-0">
          Pending
        </Badge>
      );
  }
}

export function RunbookStepList({ steps, execution, onTransition, isPending }: RunbookStepListProps) {
  const isTerminal = execution.status === "COMPLETED" || execution.status === "CANCELLED";

  return (
    <div className="space-y-2">
      {steps.map((step, index) => {
        const state: StepState = execution.step_states[step.id] ?? "PENDING";
        const transitions = STEP_TRANSITIONS[state];
        const canTransition = !isTerminal && transitions.length > 0;

        const latestTransition = [...(execution.step_history || [])]
          .reverse()
          .find((h) => String(h.step_id) === String(step.id));

        return (
          <div
            key={step.id}
            className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${
              state === "IN_PROGRESS"
                ? "border-blue-500/30 bg-blue-500/5"
                : state === "COMPLETED"
                ? "border-emerald-500/20 bg-emerald-500/5"
                : state === "SKIPPED"
                ? "border-border/50 bg-muted/20 opacity-60"
                : "border-border bg-card"
            }`}
          >
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-muted-foreground font-mono w-4 shrink-0">
                {index + 1}
              </span>
              {getStepIcon(state)}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium">{step.title}</p>
                {getStepBadge(state)}
              </div>
              {step.description && (
                <p className="text-xs text-muted-foreground mt-0.5">{step.description}</p>
              )}
              {latestTransition && (
                <p className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1.5 flex-wrap">
                  <User className="h-3 w-3 text-primary/70" />
                  <span>
                    <strong className="text-foreground">{latestTransition.actor_name || "User"}</strong>{" "}
                    {latestTransition.to === "COMPLETED" || latestTransition.to_state === "COMPLETED"
                      ? "completed this step"
                      : latestTransition.to === "IN_PROGRESS" || latestTransition.to_state === "IN_PROGRESS"
                      ? "started this step"
                      : "skipped this step"}
                  </span>
                  <span>· {new Date(latestTransition.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                </p>
              )}
            </div>

            {canTransition && (
              <div className="flex gap-1 shrink-0">
                {transitions.map((toState) => (
                  <Button
                    key={toState}
                    size="sm"
                    variant={toState === "COMPLETED" ? "default" : toState === "IN_PROGRESS" ? "secondary" : "outline"}
                    className="h-7 text-xs gap-1"
                    disabled={isPending}
                    onClick={() => onTransition(step.id, state, toState)}
                  >
                    {isPending ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : toState === "IN_PROGRESS" ? (
                      <Play className="h-3 w-3" />
                    ) : toState === "COMPLETED" ? (
                      <CheckCircle2 className="h-3 w-3" />
                    ) : (
                      <SkipForward className="h-3 w-3" />
                    )}
                    {toState === "IN_PROGRESS" ? "Start" : toState === "COMPLETED" ? "Complete" : "Skip"}
                  </Button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
