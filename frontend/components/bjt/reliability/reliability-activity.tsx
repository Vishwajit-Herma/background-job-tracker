"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ReliabilityFinding, resolveReliabilityFinding } from "@/lib/api/reliability";
import { formatReliabilityTime } from "@/lib/reliability-utils";
import { History, AlertTriangle, CheckCircle2, AlertCircle, ExternalLink, ShieldCheck, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { toastError, toastSuccess } from "@/lib/toast";

interface ReliabilityActivityProps {
  activeFindings: ReliabilityFinding[];
  recentFindings: ReliabilityFinding[];
}

function formatConditionType(type: string): string {
  switch (type) {
    case "MISSED_EXECUTION":
      return "Missed Execution";
    case "STALLED_EXECUTION":
      return "Stalled Execution";
    case "OVERDUE_EXECUTION":
      return "Queue Overdue";
    case "FAILURE_RATE_ANOMALY":
      return "Failure Rate Anomaly";
    case "RETRY_RATE_ANOMALY":
      return "Retry Rate Anomaly";
    case "DURATION_ANOMALY":
      return "Duration Anomaly";
    case "EXECUTION_VOLUME_ANOMALY":
      return "Execution Volume Anomaly";
    default:
      return type.replace(/_/g, " ");
  }
}

export function ReliabilityActivity({ activeFindings, recentFindings }: ReliabilityActivityProps) {
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const router = useRouter();

  const handleResolve = async (findingId: number) => {
    try {
      setResolvingId(findingId);
      await resolveReliabilityFinding(findingId);
      toastSuccess("Reliability finding resolved");
      router.refresh();
    } catch (err: any) {
      toastError("Failed to resolve finding", err);
    } finally {
      setResolvingId(null);
    }
  };

  // Combine findings removing duplicates (active findings first)
  const allFindingsMap = new Map<number, ReliabilityFinding>();
  activeFindings.forEach((f) => allFindingsMap.set(f.id, f));
  recentFindings.forEach((f) => {
    if (!allFindingsMap.has(f.id)) {
      allFindingsMap.set(f.id, f);
    }
  });

  const findingsList = Array.from(allFindingsMap.values()).sort(
    (a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime()
  );

  return (
    <Card className="shadow-sm border-border/80">
      <CardHeader className="pb-3 border-b bg-muted/20">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <History className="h-4 w-4 text-primary" /> Reliability Activity
          </CardTitle>
          <span className="text-xs text-muted-foreground">Reliability findings & recovery history</span>
        </div>
      </CardHeader>

      <CardContent className="pt-4">
        {findingsList.length === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center space-y-2 bg-muted/10">
            <ShieldCheck className="h-8 w-8 mx-auto text-emerald-500/70" />
            <h4 className="text-sm font-semibold text-foreground">No reliability issues detected</h4>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              This job is currently operating within its expected behavior. Reliability events and findings will appear here when anomalies occur.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {findingsList.map((finding) => {
              const isActive = finding.status === "ACTIVE";
              const detectedTime = formatReliabilityTime(finding.detected_at);
              const recoveredTime = formatReliabilityTime(finding.recovered_at);

              return (
                <div
                  key={finding.id}
                  className={cn(
                    "p-3.5 rounded-lg border transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-sm",
                    isActive
                      ? "border-amber-500/30 bg-amber-500/5 dark:bg-amber-500/10"
                      : "border-border bg-card/60"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 shrink-0">
                      {isActive ? (
                        finding.condition_type === "STALLED_EXECUTION" ? (
                          <AlertCircle className="h-4 w-4 text-destructive" />
                        ) : (
                          <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                        )
                      ) : (
                        <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                      )}
                    </div>

                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-foreground">
                          {formatConditionType(finding.condition_type)}
                        </span>
                        {isActive ? (
                          <Badge variant="warning" className="text-[10px] px-1.5 py-0">
                            Active
                          </Badge>
                        ) : (
                          <Badge variant="success" className="text-[10px] px-1.5 py-0">
                            Recovered
                          </Badge>
                        )}
                        <Badge
                          variant={finding.severity === "CRITICAL" ? "destructive" : "secondary"}
                          className="text-[10px] px-1.5 py-0 uppercase"
                        >
                          {finding.severity}
                        </Badge>
                      </div>

                      {/* Detail / Reason */}
                      <p className="text-xs text-muted-foreground">
                        {isActive ? (
                          finding.details && Object.keys(finding.details).length > 0 ? (
                            JSON.stringify(finding.details).replace(/[{"}]/g, " ").trim()
                          ) : (
                            "Abnormal reliability condition detected."
                          )
                        ) : (
                          finding.recovery_reason || "Recovered to normal behavior."
                        )}
                      </p>

                      <div className="flex items-center gap-3 text-[11px] text-muted-foreground pt-0.5">
                        <span title={detectedTime.exact}>Detected: {detectedTime.relative}</span>
                        {!isActive && finding.recovered_at && (
                          <span title={recoveredTime.exact}>• Recovered: {recoveredTime.relative}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center gap-2 sm:text-right shrink-0">
                    {isActive && (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={resolvingId === finding.id}
                        onClick={() => handleResolve(finding.id)}
                        className="h-7 text-xs gap-1.5 shadow-none hover:bg-emerald-50 dark:hover:bg-emerald-950/30 hover:text-emerald-600 dark:hover:text-emerald-400 hover:border-emerald-200 dark:hover:border-emerald-800"
                      >
                        {resolvingId === finding.id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <CheckCircle2 className="h-3 w-3" />
                        )}
                        {resolvingId === finding.id ? "Resolving..." : "Resolve"}
                      </Button>
                    )}
                    {finding.incident && (
                      <Link href={`/incidents/${finding.incident}`}>
                        <Button variant="outline" size="sm" className="h-7 text-xs gap-1.5 shadow-none">
                          <ExternalLink className="h-3 w-3" /> View Incident #{finding.incident}
                        </Button>
                      </Link>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
