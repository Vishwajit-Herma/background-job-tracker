"use client";

import { ReliabilityReport } from "@/lib/api/projects";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ShieldCheck, Timer, HeartPulse, AlertTriangle, CheckCircle2, InfoIcon, Loader2 } from "lucide-react";
import Link from "next/link";

interface ReliabilityReportCardProps {
  report?: ReliabilityReport | null;
  isLoading: boolean;
}

function formatSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${Math.round(seconds % 60)}s`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${minutes % 60}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

export function ReliabilityReportCard({ report, isLoading }: ReliabilityReportCardProps) {
  if (isLoading) {
    return (
      <Card className="col-span-2">
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            <CardTitle>Reliability & Recovery (MTTR / MTBF)</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="h-48 flex items-center justify-center text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mr-2" /> Loading reliability report…
        </CardContent>
      </Card>
    );
  }

  if (!report) {
    return null;
  }

  const perJob = report.per_job || (report as any).by_job || [];

  const totalIncidents = report.total_incidents ?? 0;
  const resolvedIncidents = report.resolved_incidents ?? 0;

  const resolutionRate =
    totalIncidents > 0
      ? `${Math.round((resolvedIncidents / totalIncidents) * 100)}%`
      : "100%";

  return (
    <Card className="col-span-2">
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            <div>
              <CardTitle className="text-base font-semibold">Reliability & Recovery (MTTR / MTBF)</CardTitle>
              <CardDescription className="text-xs mt-0.5">
                Incident recovery velocity and operational stability metrics for this time window.
              </CardDescription>
            </div>
          </div>
          {report.start && report.end && (
            <Badge variant="outline" className="w-fit text-xs font-normal text-muted-foreground">
              {new Date(report.start).toLocaleDateString()} – {new Date(report.end).toLocaleDateString()}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Metric summary grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl border bg-card shadow-sm space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">MTTR</span>
              <Timer className="h-4 w-4 text-primary" />
            </div>
            <p className="text-2xl font-bold tracking-tight font-mono">
              {formatSeconds(report.mttr_seconds)}
            </p>
            <p className="text-[11px] text-muted-foreground">
              Mean Time to Resolve
            </p>
          </div>

          <div className="p-4 rounded-xl border bg-card shadow-sm space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">MTBF</span>
              <HeartPulse className="h-4 w-4 text-emerald-500" />
            </div>
            <p className="text-2xl font-bold tracking-tight font-mono">
              {formatSeconds(report.mtbf_seconds)}
            </p>
            <p className="text-[11px] text-muted-foreground">
              Mean Time Between Failures
            </p>
          </div>

          <div className="p-4 rounded-xl border bg-card shadow-sm space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Total Incidents</span>
              <AlertTriangle className="h-4 w-4 text-amber-500" />
            </div>
            <p className="text-2xl font-bold tracking-tight font-mono">
              {totalIncidents}
            </p>
            <p className="text-[11px] text-muted-foreground">
              During selected period
            </p>
          </div>

          <div className="p-4 rounded-xl border bg-card shadow-sm space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Resolution Rate</span>
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            </div>
            <p className="text-2xl font-bold tracking-tight font-mono">
              {resolutionRate}
            </p>
            <p className="text-[11px] text-muted-foreground">
              {resolvedIncidents} of {totalIncidents} resolved
            </p>
          </div>
        </div>

        {/* Per-Job Reliability Breakdown Table */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold">Per-Job Reliability Breakdown</h4>
            <span className="text-xs text-muted-foreground">
              {perJob.length} job{perJob.length !== 1 ? "s" : ""} recorded
            </span>
          </div>

          {perJob.length === 0 ? (
            <div className="flex items-center justify-center h-24 text-sm text-muted-foreground italic border border-dashed rounded-lg">
              No job-specific incidents recorded in this timeframe.
            </div>
          ) : (
            <div className="rounded-lg border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40">
                    <TableHead className="text-xs font-semibold">Job</TableHead>
                    <TableHead className="text-xs font-semibold">Identifier</TableHead>
                    <TableHead className="text-xs font-semibold text-right">Incidents</TableHead>
                    <TableHead className="text-xs font-semibold text-right">Resolved</TableHead>
                    <TableHead className="text-xs font-semibold text-right">MTTR</TableHead>
                    <TableHead className="text-xs font-semibold text-right">MTBF</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {perJob.map((job: any) => (
                    <TableRow key={job.job_id} className="hover:bg-muted/30">
                      <TableCell className="font-medium text-sm">
                        <Link href={`/jobs?job_id=${job.job_id}`} className="hover:underline text-primary">
                          {job.job_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-xs font-mono text-muted-foreground max-w-[200px] truncate">
                        {job.task_identifier}
                      </TableCell>
                      <TableCell className="text-sm font-mono text-right">
                        {job.total_incidents}
                      </TableCell>
                      <TableCell className="text-sm font-mono text-right text-emerald-600 dark:text-emerald-400">
                        {job.resolved_incidents}
                      </TableCell>
                      <TableCell className="text-sm font-mono text-right">
                        {formatSeconds(job.mttr_seconds)}
                      </TableCell>
                      <TableCell className="text-sm font-mono text-right">
                        {formatSeconds(job.mtbf_seconds)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
