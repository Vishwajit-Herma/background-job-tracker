"use client";

import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { JobReliabilityOverview } from "@/lib/api/reliability";
import { Activity, ArrowUpRight, CheckCircle2, Zap } from "lucide-react";

interface BehaviorAnomalyCardProps {
  reliability: JobReliabilityOverview;
}

export function BehaviorAnomalyCard({ reliability }: BehaviorAnomalyCardProps) {
  const { baseline, behavior_comparison, active_anomalies } = reliability;
  const isBaselineSufficient = baseline?.is_sufficient ?? false;

  const failureRate = behavior_comparison?.failure_rate;
  const retryRate = behavior_comparison?.retry_rate;
  const p95Duration = behavior_comparison?.p95_duration_ms;
  const volume = behavior_comparison?.hourly_volume;

  return (
    <Card className="border shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Activity className="h-4.5 w-4.5 text-primary" />
              Behavior & Anomaly Detection
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground mt-0.5">
              Current 60-minute behavior evaluated against 7-day statistical baseline.
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            {active_anomalies.length > 0 ? (
              <Badge variant="destructive" className="bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/20 text-xs gap-1 py-0.5">
                <Zap className="h-3 w-3 fill-current" />
                {active_anomalies.length} Active {active_anomalies.length === 1 ? "Anomaly" : "Anomalies"}
              </Badge>
            ) : isBaselineSufficient ? (
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-xs gap-1 py-0.5">
                <CheckCircle2 className="h-3 w-3" />
                Normal Behavior
              </Badge>
            ) : (
              <Badge variant="outline" className="text-xs text-muted-foreground py-0.5">
                Baseline Insufficient
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-1">
        {/* Active Anomaly Alerts Banner */}
        {active_anomalies.length > 0 && (
          <div className="space-y-2">
            {active_anomalies.map((anomaly) => {
              const details = (anomaly.details || {}) as Record<string, any>;
              return (
                <div
                  key={anomaly.id}
                  className="rounded-lg border border-purple-500/30 bg-purple-500/5 p-3 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-purple-900 dark:text-purple-300 flex items-center gap-1.5">
                      <Zap className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400" />
                      {anomaly.condition_type.replace(/_/g, " ")} Detected
                    </span>
                    {anomaly.incident && (
                      <Link
                        href={`/incidents/${anomaly.incident}`}
                        className="font-medium text-primary hover:underline inline-flex items-center gap-0.5 text-[11px]"
                      >
                        View Incident #{anomaly.incident} <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                  <p className="text-muted-foreground text-[11px]">
                    Observed <span className="font-semibold text-foreground">{details.current_value ?? "—"}</span> vs baseline <span className="font-semibold text-foreground">{details.baseline_value ?? "—"}</span>
                    {details.deviation_ratio && (
                      <> (<span className="text-purple-700 dark:text-purple-400 font-semibold">{details.deviation_ratio}× above normal</span>)</>
                    )}
                    {details.adaptive_threshold !== undefined && (
                      <> • Adaptive Threshold: {details.adaptive_threshold}</>
                    )}
                  </p>
                </div>
              );
            })}
          </div>
        )}

        {/* 4-Metric Grid Comparison */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Failure Rate */}
          <div className="p-3 rounded-lg border bg-card/60 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-medium">Failure Rate</span>
              {failureRate?.deviation_ratio && failureRate.deviation_ratio >= 3.0 && (
                <span className="text-[10px] font-semibold text-purple-600 bg-purple-500/10 px-1.5 py-0.5 rounded">
                  {failureRate.deviation_ratio}×
                </span>
              )}
            </div>
            <div>
              <div className="text-xl font-bold">
                {failureRate?.current !== null && failureRate?.current !== undefined ? `${failureRate.current}%` : "—"}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Baseline: {failureRate?.baseline !== null && failureRate?.baseline !== undefined ? `${failureRate.baseline}%` : "—"}
              </div>
              {failureRate?.adaptive_threshold !== null && failureRate?.adaptive_threshold !== undefined && (
                <div className="text-[10px] text-muted-foreground/80 mt-0.5">
                  Adaptive: ≤ {failureRate.adaptive_threshold}%
                </div>
              )}
            </div>
          </div>

          {/* Retry Rate */}
          <div className="p-3 rounded-lg border bg-card/60 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-medium">Retry Rate</span>
              {retryRate?.deviation_ratio && retryRate.deviation_ratio >= 3.0 && (
                <span className="text-[10px] font-semibold text-purple-600 bg-purple-500/10 px-1.5 py-0.5 rounded">
                  {retryRate.deviation_ratio}×
                </span>
              )}
            </div>
            <div>
              <div className="text-xl font-bold">
                {retryRate?.current !== null && retryRate?.current !== undefined ? `${retryRate.current}%` : "—"}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Baseline: {retryRate?.baseline !== null && retryRate?.baseline !== undefined ? `${retryRate.baseline}%` : "—"}
              </div>
              {retryRate?.adaptive_threshold !== null && retryRate?.adaptive_threshold !== undefined && (
                <div className="text-[10px] text-muted-foreground/80 mt-0.5">
                  Adaptive: ≤ {retryRate.adaptive_threshold}%
                </div>
              )}
            </div>
          </div>

          {/* P95 Duration */}
          <div className="p-3 rounded-lg border bg-card/60 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-medium">P95 Duration</span>
              {p95Duration?.deviation_ratio && p95Duration.deviation_ratio >= 2.5 && (
                <span className="text-[10px] font-semibold text-purple-600 bg-purple-500/10 px-1.5 py-0.5 rounded">
                  {p95Duration.deviation_ratio}×
                </span>
              )}
            </div>
            <div>
              <div className="text-xl font-bold">
                {p95Duration?.current !== null && p95Duration?.current !== undefined
                  ? p95Duration.current >= 1000 ? `${(p95Duration.current / 1000).toFixed(2)}s` : `${Math.round(p95Duration.current)}ms`
                  : "—"}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Baseline: {p95Duration?.baseline !== null && p95Duration?.baseline !== undefined
                  ? p95Duration.baseline >= 1000 ? `${(p95Duration.baseline / 1000).toFixed(2)}s` : `${Math.round(p95Duration.baseline)}ms`
                  : "—"}
              </div>
              {p95Duration?.adaptive_threshold !== null && p95Duration?.adaptive_threshold !== undefined && (
                <div className="text-[10px] text-muted-foreground/80 mt-0.5">
                  Adaptive: ≤ {p95Duration.adaptive_threshold >= 1000 ? `${(p95Duration.adaptive_threshold / 1000).toFixed(2)}s` : `${Math.round(p95Duration.adaptive_threshold)}ms`}
                </div>
              )}
            </div>
          </div>

          {/* Hourly Volume */}
          <div className="p-3 rounded-lg border bg-card/60 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-medium">Hourly Volume (60m)</span>
              {volume?.deviation_ratio && (volume.deviation_ratio >= 4.0 || volume.deviation_ratio <= 0.2) && (
                <span className="text-[10px] font-semibold text-purple-600 bg-purple-500/10 px-1.5 py-0.5 rounded">
                  {volume.deviation_ratio}×
                </span>
              )}
            </div>
            <div>
              <div className="text-xl font-bold">
                {volume?.current !== null && volume?.current !== undefined ? volume.current : 0} <span className="text-xs font-normal text-muted-foreground">execs</span>
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Baseline: {volume?.baseline !== null && volume?.baseline !== undefined ? `${volume.baseline}/hr` : "—"}
              </div>
              <div className="text-[10px] text-muted-foreground/80 mt-0.5">
                Compared with historical average hourly volume.
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
