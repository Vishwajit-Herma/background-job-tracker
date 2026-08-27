"use client";

import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { IncidentCorrelation } from "@/lib/api/incidents";
import { GitFork, Link2, ShieldAlert, Cpu, Layers, AlertTriangle, ArrowUpRight } from "lucide-react";

interface IncidentCorrelationsCardProps {
  correlations: IncidentCorrelation[];
  jobId?: number | null;
  projectId?: number;
}

function getTargetBadge(targetType: string) {
  switch (targetType) {
    case "FINDING":
      return (
        <Badge variant="outline" className="text-[10px] py-0.5 px-2 gap-1 uppercase tracking-wider font-semibold font-mono border-purple-500/30 text-purple-700 dark:text-purple-400 bg-purple-500/5">
          <AlertTriangle className="h-3 w-3" />
          Finding
        </Badge>
      );
    case "WORKER":
      return (
        <Badge variant="outline" className="text-[10px] py-0.5 px-2 gap-1 uppercase tracking-wider font-semibold font-mono border-blue-500/30 text-blue-700 dark:text-blue-400 bg-blue-500/5">
          <Cpu className="h-3 w-3" />
          Worker
        </Badge>
      );
    case "QUEUE":
      return (
        <Badge variant="outline" className="text-[10px] py-0.5 px-2 gap-1 uppercase tracking-wider font-semibold font-mono border-amber-500/30 text-amber-700 dark:text-amber-400 bg-amber-500/5">
          <Layers className="h-3 w-3" />
          Queue
        </Badge>
      );
    case "INCIDENT":
      return (
        <Badge variant="outline" className="text-[10px] py-0.5 px-2 gap-1 uppercase tracking-wider font-semibold font-mono border-destructive/30 text-destructive bg-destructive/5">
          <ShieldAlert className="h-3 w-3" />
          Incident
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="text-[10px] py-0.5 px-2 gap-1 uppercase tracking-wider font-semibold font-mono">
          <Link2 className="h-3 w-3" />
          Signal
        </Badge>
      );
  }
}

function getCorrelationUrl(corr: IncidentCorrelation, jobId?: number | null) {
  switch (corr.target_type) {
    case "INCIDENT":
      return corr.target_id ? `/incidents/${corr.target_id}` : "/incidents";
    case "FINDING":
      return jobId ? `/jobs/${jobId}/reliability` : "/jobs";
    case "WORKER":
      return `/executions?search=${encodeURIComponent(corr.target_name)}`;
    case "QUEUE":
      return `/executions?search=${encodeURIComponent(corr.target_name)}`;
    default:
      return null;
  }
}

export function IncidentCorrelationsCard({ correlations, jobId, projectId }: IncidentCorrelationsCardProps) {
  return (
    <Card className="border shadow-sm bg-gradient-to-b from-card to-card/70">
      <CardHeader className="pb-3.5">
        <div className="flex items-center justify-between gap-2">
          <div className="space-y-0.5">
            <CardTitle className="text-base font-semibold flex items-center gap-2 text-foreground">
              <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
                <GitFork className="h-4 w-4" />
              </div>
              Correlated Project Signals
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              Concurrent anomalies, shared worker execution nodes, and queue cascades.
            </CardDescription>
          </div>
          <Badge variant="outline" className="text-xs px-2.5 py-0.5 font-medium bg-muted/30">
            {correlations.length} {correlations.length === 1 ? "Signal" : "Signals"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-2.5 pt-0">
        {correlations.length === 0 ? (
          <div className="p-6 text-center text-xs text-muted-foreground bg-muted/20 rounded-xl border border-dashed flex flex-col items-center justify-center gap-2">
            <GitFork className="h-6 w-6 text-muted-foreground/60" />
            <span>No correlated anomalies or cascading signals detected across the project.</span>
          </div>
        ) : (
          correlations.map((corr, idx) => {
            const linkUrl = getCorrelationUrl(corr, jobId);
            const content = (
              <div
                className={`p-3.5 rounded-xl border bg-card/90 shadow-sm transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
                  linkUrl ? "hover:border-primary/40 hover:bg-primary/5 cursor-pointer group" : ""
                }`}
              >
                <div className="space-y-1.5 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    {getTargetBadge(corr.target_type)}
                    <span className="font-semibold font-mono text-sm text-foreground break-all group-hover:text-primary transition-colors flex items-center gap-1.5">
                      <span>{corr.target_name}</span>
                      {linkUrl && <ArrowUpRight className="h-3 w-3 text-primary opacity-0 group-hover:opacity-100 transition-opacity" />}
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1.5 pt-0.5">
                    {corr.reasons.map((reason, rIdx) => (
                      <span
                        key={rIdx}
                        className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-muted/60 text-muted-foreground border border-border/40"
                      >
                        {reason}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="shrink-0 self-start sm:self-auto">
                  <Badge
                    variant="outline"
                    className={`text-xs py-1 px-2.5 font-semibold ${
                      corr.correlation_strength === "STRONG"
                        ? "border-emerald-500/30 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 shadow-sm"
                        : "border-border text-muted-foreground bg-muted/30"
                    }`}
                  >
                    {corr.correlation_strength === "STRONG" ? "Strong Correlation" : "Moderate Match"}
                  </Badge>
                </div>
              </div>
            );

            return linkUrl ? (
              <Link key={idx} href={linkUrl} className="block">
                {content}
              </Link>
            ) : (
              <div key={idx}>{content}</div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
