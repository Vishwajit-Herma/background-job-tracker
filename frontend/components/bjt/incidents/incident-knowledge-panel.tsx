"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getIncidentKnowledge } from "@/lib/api/incidents";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Brain,
  CheckCircle2,
  Circle,
  ChevronDown,
  ChevronUp,
  Loader2,
  Database,
} from "lucide-react";

interface IncidentKnowledgePanelProps {
  incidentId: number;
}

export function IncidentKnowledgePanel({ incidentId }: IncidentKnowledgePanelProps) {
  const [showRaw, setShowRaw] = useState(false);

  const { data: knowledge, isLoading, isError } = useQuery({
    queryKey: ["incident-knowledge", incidentId],
    queryFn: () => getIncidentKnowledge(incidentId),
    enabled: !!incidentId,
    staleTime: 30_000,
  });

  const checks = [
    {
      label: "Incident facts",
      done: !!knowledge?.incident,
      detail: knowledge?.incident
        ? `INC-${knowledge.incident.id} · ${knowledge.incident.status} · ${knowledge.incident.severity}`
        : null,
    },
    {
      label: "Timeline events",
      done: !!(knowledge?.events && knowledge.events.length > 0),
      detail: knowledge?.events ? `${knowledge.events.length} events` : null,
    },
    {
      label: "Intelligence analysis",
      done: !!(knowledge?.intelligence && knowledge.intelligence.status === "READY"),
      detail: knowledge?.intelligence
        ? knowledge.intelligence.status === "READY"
          ? `${knowledge.intelligence.probable_causes.length} probable cause(s)`
          : "Pending"
        : "Not yet computed",
    },
    {
      label: "Runbook executions",
      done: !!(knowledge?.runbook_executions && knowledge.runbook_executions.length > 0),
      detail: knowledge?.runbook_executions
        ? `${knowledge.runbook_executions.length} execution(s)`
        : null,
    },
    {
      label: "Postmortem",
      done: !!(knowledge?.postmortem),
      detail: knowledge?.postmortem
        ? `Status: ${knowledge.postmortem.status}`
        : "Not started",
    },
  ];

  const completedCount = checks.filter((c) => c.done).length;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-40 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" /> Assembling knowledge artifact…
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-40 text-destructive text-sm">
        Failed to load knowledge artifact.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-primary" />
          <h3 className="font-semibold">Incident Knowledge Artifact</h3>
          <Badge className="bg-violet-500/10 text-violet-700 dark:text-violet-400 border-violet-500/20 text-xs">
            AI Ready
          </Badge>
        </div>
        <span className="text-xs text-muted-foreground">
          {completedCount}/{checks.length} components
        </span>
      </div>

      <p className="text-xs text-muted-foreground">
        This structured knowledge artifact combines all incident data — facts, timeline, intelligence,
        runbook executions, and postmortem — for consumption by AI analysis.
      </p>

      {/* Checklist */}
      <div className="space-y-2">
        {checks.map((check) => (
          <div
            key={check.label}
            className={`flex items-center gap-3 p-3 rounded-lg border ${
              check.done
                ? "border-emerald-500/20 bg-emerald-500/5"
                : "border-border bg-muted/10"
            }`}
          >
            {check.done ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
            ) : (
              <Circle className="h-4 w-4 text-muted-foreground shrink-0" />
            )}
            <div className="flex-1">
              <p className="text-sm font-medium">{check.label}</p>
              {check.detail && (
                <p className="text-xs text-muted-foreground">{check.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Raw JSON toggle */}
      {knowledge && (
        <div className="space-y-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs gap-1"
            onClick={() => setShowRaw(!showRaw)}
          >
            <Database className="h-3 w-3" />
            {showRaw ? "Hide" : "View"} Structured Knowledge
            {showRaw ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </Button>

          {showRaw && (
            <pre className="text-[10px] font-mono p-4 rounded-lg border bg-muted/30 overflow-auto max-h-[500px] whitespace-pre-wrap break-all">
              {JSON.stringify(knowledge, null, 2)}
            </pre>
          )}
        </div>
      )}

      {knowledge && (
        <p className="text-[10px] text-muted-foreground">
          Last refreshed: {new Date().toLocaleTimeString()}
        </p>
      )}
    </div>
  );
}
