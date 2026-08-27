"use client";

import { useQuery } from "@tanstack/react-query";
import { getIncidentIntelligence, IncidentIntelligence } from "@/lib/api/incidents";
import { IncidentImpactCard } from "./incident-impact-card";
import { IncidentProbableCauseCard } from "./incident-probable-cause-card";
import { IncidentCorrelationsCard } from "./incident-correlations-card";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Sparkles, Binary } from "lucide-react";

interface IncidentIntelligenceSectionProps {
  incidentId: number;
  jobId?: number | null;
  projectId?: number;
}

export function IncidentIntelligenceSection({ incidentId, jobId, projectId }: IncidentIntelligenceSectionProps) {
  const { data: intelligence, isLoading, isError } = useQuery<IncidentIntelligence>({
    queryKey: ["incident-intelligence", incidentId],
    queryFn: () => getIncidentIntelligence(incidentId),
    enabled: !!incidentId,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === "PENDING" ? 2500 : false;
    },
  });

  if (isLoading || intelligence?.status === "PENDING") {
    return (
      <Card className="border border-dashed border-primary/30 bg-primary/5 shadow-sm overflow-hidden relative">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-primary/10 to-primary/5 animate-pulse" />
        <CardContent className="p-6 relative flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="p-3 rounded-xl bg-primary/10 text-primary border border-primary/20 shadow-inner">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
            <div>
              <div className="text-sm font-semibold flex items-center gap-2 text-foreground">
                <Sparkles className="h-4 w-4 text-primary" />
                Analyzing Incident Telemetry & Root Cause...
              </div>
              <p className="text-xs text-muted-foreground mt-0.5 max-w-xl">
                Evaluating deterministic failure concentrations, baseline multipliers, and correlating project-wide signals.
              </p>
            </div>
          </div>

          <Badge variant="outline" className="text-xs px-2.5 py-1 bg-card/60 backdrop-blur font-mono">
            Async Ingestion
          </Badge>
        </CardContent>
      </Card>
    );
  }

  if (isError || !intelligence) {
    return null;
  }

  return (
    <div className="space-y-3.5">
      {/* Subtle section label */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded bg-primary/10 text-primary">
            <Sparkles className="h-3.5 w-3.5" />
          </div>
          <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Incident Intelligence & Diagnostics
          </span>
        </div>
        <Badge variant="outline" className="text-[11px] font-mono px-2 py-0.5 text-muted-foreground bg-muted/30">
          Engine v{intelligence.analysis_version || "1.0"}
        </Badge>
      </div>

      {/* Probable Root Cause & Impact Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch">
        {intelligence.probable_causes && (
          <IncidentProbableCauseCard
            probableCauses={intelligence.probable_causes}
            jobId={jobId}
            projectId={projectId}
          />
        )}
        {intelligence.impact && (
          <IncidentImpactCard impact={intelligence.impact} />
        )}
      </div>

      {/* Correlated Signals */}
      {intelligence.correlations && (
        <IncidentCorrelationsCard
          correlations={intelligence.correlations}
          jobId={jobId}
          projectId={projectId}
        />
      )}
    </div>
  );
}
