"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Briefcase, ListChecks, Activity, LineChart, ShieldCheck, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { ReliabilityBadge } from "@/components/bjt/reliability/reliability-badge";
import { ReliabilityState } from "@/lib/api/reliability";

interface JobHeaderProps {
  job: {
    id: number;
    name: string;
    task_identifier: string;
    status?: string;
    operational_status?: "CRITICAL" | "DEGRADED" | "HEALTHY";
    reliability_state?: ReliabilityState | "DISABLED";
    project_id?: number;
    project_name?: string;
  };
}

export function JobHeader({ job }: JobHeaderProps) {
  const pathname = usePathname();
  const router = useRouter();

  const tabs = [
    { label: "Overview", href: `/jobs/${job.id}`, exact: true, icon: ListChecks },
    { label: "Reliability", href: `/jobs/${job.id}/reliability`, exact: false, icon: ShieldCheck },
    { label: "Analytics", href: `/jobs/${job.id}/analytics`, exact: false, icon: LineChart },
    { label: "Executions", href: `/jobs/${job.id}/executions`, exact: false, icon: Activity },
  ];

  const isTabActive = (href: string, exact: boolean) => {
    if (exact) return pathname === href;
    return pathname.startsWith(href);
  };

  return (
    <div className="space-y-4 border-b pb-1">
      {/* Breadcrumbs & Back Button */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs -ml-2 text-muted-foreground hover:text-foreground"
          onClick={() => router.push("/jobs")}
        >
          <ArrowLeft className="mr-1 h-3.5 w-3.5" /> Back to Jobs
        </Button>
        <ChevronRight className="h-3 w-3 opacity-40" />
        {job.project_name && (
          <>
            <span className="flex items-center gap-1">
              <Briefcase className="h-3 w-3" /> {job.project_name}
            </span>
            <ChevronRight className="h-3 w-3 opacity-40" />
          </>
        )}
        <span className="font-medium text-foreground">{job.name}</span>
      </div>

      {/* Main Title & Status Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">{job.name}</h1>
            {job.status === "inactive" && (
              <Badge variant="secondary" className="text-[10px] uppercase">
                Inactive
              </Badge>
            )}
            {job.reliability_state && (
              <ReliabilityBadge state={job.reliability_state} clickable={false} />
            )}
            {job.operational_status === "CRITICAL" ? (
              <Badge variant="destructive" className="text-[10px] uppercase">
                Critical Incident
              </Badge>
            ) : job.operational_status === "DEGRADED" ? (
              <Badge variant="warning" className="text-[10px] uppercase">
                Degraded
              </Badge>
            ) : null}
          </div>
          <p className="text-xs font-mono text-muted-foreground bg-muted/50 px-2 py-0.5 rounded w-fit inline-block">
            {job.task_identifier}
          </p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-1 pt-2 -mb-px">
        {tabs.map((tab) => {
          const active = isTabActive(tab.href, tab.exact);
          const Icon = tab.icon;

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "flex items-center gap-2 px-3.5 py-2 text-sm font-medium border-b-2 transition-all hover:text-foreground",
                active
                  ? "border-primary text-primary font-semibold"
                  : "border-transparent text-muted-foreground hover:border-border"
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
