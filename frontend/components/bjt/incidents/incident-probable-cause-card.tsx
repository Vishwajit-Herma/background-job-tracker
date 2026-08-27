"use client";

import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ProbableCauseCandidate, ConfidenceLevel } from "@/lib/api/incidents";
import { Cpu, Layers, Activity, Zap, HelpCircle, CheckCircle2, Sparkles, ShieldAlert, ArrowUpRight } from "lucide-react";

interface IncidentProbableCauseCardProps {
  probableCauses: ProbableCauseCandidate[];
  jobId?: number | null;
  projectId?: number;
}

function getConfidenceBadge(confidence: ConfidenceLevel) {
  switch (confidence) {
    case "HIGH":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 shadow-sm shrink-0">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          High Confidence
        </span>
      );
    case "MEDIUM":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 shadow-sm shrink-0">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
          Medium Confidence
        </span>
      );
    case "LOW":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-700 dark:text-slate-400 border border-slate-500/20 shadow-sm shrink-0">
          <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
          Low Confidence
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-muted text-muted-foreground border border-border shadow-sm shrink-0">
          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground" />
          Insufficient Evidence
        </span>
      );
  }
}

function getCandidateBorderColor(confidence: ConfidenceLevel) {
  switch (confidence) {
    case "HIGH":
      return "border-l-4 border-l-emerald-500 dark:border-l-emerald-400";
    case "MEDIUM":
      return "border-l-4 border-l-amber-500 dark:border-l-amber-400";
    case "LOW":
      return "border-l-4 border-l-slate-400 dark:border-l-slate-500";
    default:
      return "border-l-4 border-l-muted-foreground";
  }
}

function getCandidateIcon(candidate: string) {
  switch (candidate) {
    case "WORKER":
      return <Cpu className="h-4 w-4 text-purple-600 dark:text-purple-400" />;
    case "QUEUE":
      return <Layers className="h-4 w-4 text-amber-600 dark:text-amber-400" />;
    case "JOB":
      return <Activity className="h-4 w-4 text-blue-600 dark:text-blue-400" />;
    case "ANOMALY":
      return <Zap className="h-4 w-4 text-destructive" />;
    default:
      return <HelpCircle className="h-4 w-4 text-muted-foreground" />;
  }
}

function getCandidateActionUrl(candidate: string, value: string, jobId?: number | null) {
  switch (candidate) {
    case "WORKER":
      return `/executions?search=${encodeURIComponent(value)}`;
    case "QUEUE":
      return `/executions?search=${encodeURIComponent(value)}`;
    case "JOB":
      return jobId ? `/jobs/${jobId}/reliability` : "/jobs";
    case "ANOMALY":
      return jobId ? `/jobs/${jobId}/reliability` : "/jobs";
    default:
      return null;
  }
}

export function IncidentProbableCauseCard({ probableCauses, jobId, projectId }: IncidentProbableCauseCardProps) {
  return (
    <Card className="border shadow-sm bg-gradient-to-b from-card to-card/70 flex flex-col justify-between">
      <CardHeader className="pb-3.5">
        <div className="flex items-center justify-between gap-2">
          <div className="space-y-0.5">
            <CardTitle className="text-base font-semibold flex items-center gap-2 text-foreground">
              <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
                <Sparkles className="h-4 w-4" />
              </div>
              Probable Root Cause
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              Ranked candidates derived from execution & anomaly telemetry.
            </CardDescription>
          </div>

          <Badge variant="outline" className="text-xs px-2 py-0.5 font-medium bg-muted/30">
            {probableCauses.length} {probableCauses.length === 1 ? "Candidate" : "Candidates"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3 pt-0 flex-1">
        {probableCauses.length === 0 ? (
          <div className="p-6 text-center text-xs text-muted-foreground bg-muted/20 rounded-xl border border-dashed flex flex-col items-center justify-center gap-2">
            <ShieldAlert className="h-6 w-6 text-muted-foreground/60" />
            <span>No definitive root cause candidates identified.</span>
          </div>
        ) : (
          probableCauses.map((cause, idx) => {
            const actionUrl = getCandidateActionUrl(cause.candidate, cause.value, jobId);
            return (
              <div
                key={idx}
                className={`p-4 rounded-xl border bg-card/90 shadow-sm transition-all hover:shadow-md ${getCandidateBorderColor(
                  cause.confidence
                )} space-y-3`}
              >
                {/* Header row: Icon, Type, Value & Confidence Badge */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2.5">
                  <div className="flex items-start gap-2.5 min-w-0">
                    <div className="p-2 rounded-lg bg-muted/60 border shrink-0 mt-0.5">
                      {getCandidateIcon(cause.candidate)}
                    </div>
                    <div className="min-w-0 space-y-0.5">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                          {cause.candidate}
                        </span>
                      </div>
                      <p className="text-sm font-semibold font-mono text-foreground break-all leading-tight">
                        {cause.value}
                      </p>
                    </div>
                  </div>

                  <div className="shrink-0 self-start sm:self-auto">
                    {getConfidenceBadge(cause.confidence)}
                  </div>
                </div>

                {/* Evidence Section */}
                {cause.evidence && cause.evidence.length > 0 && (
                  <div className="pt-2 border-t border-border/60 space-y-1.5">
                    <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                      Diagnostic Evidence
                    </div>
                    <div className="space-y-1.5">
                      {cause.evidence.map((item, eIdx) => (
                        <div
                          key={eIdx}
                          className="flex items-start gap-2 text-xs bg-muted/30 p-2 rounded-lg border border-border/40 text-foreground/90 leading-relaxed"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                          <span className="flex-1">{item}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Direct Action Link */}
                {actionUrl && (
                  <div className="pt-1 flex justify-end">
                    <Link
                      href={actionUrl}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
                    >
                      <span>Investigate {cause.candidate.toLowerCase()} telemetry</span>
                      <ArrowUpRight className="h-3 w-3" />
                    </Link>
                  </div>
                )}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
