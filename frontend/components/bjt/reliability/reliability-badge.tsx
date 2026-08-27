"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ReliabilityState } from "@/lib/api/reliability";
import { cn } from "@/lib/utils";
import { CheckCircle2, AlertTriangle, Clock, AlertCircle, ShieldOff } from "lucide-react";

interface ReliabilityBadgeProps {
  state: ReliabilityState | "DISABLED";
  jobId?: number;
  clickable?: boolean;
  className?: string;
  size?: "sm" | "default" | "lg";
}

const STATE_CONFIG: Record<
  ReliabilityState | "DISABLED",
  {
    label: string;
    description: string;
    variantClass: string;
    dotClass: string;
    icon: typeof CheckCircle2;
  }
> = {
  HEALTHY: {
    label: "Healthy",
    description: "The job is currently executing within its expected reliability behavior.",
    variantClass: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20",
    dotClass: "bg-emerald-500",
    icon: CheckCircle2,
  },
  MISSED: {
    label: "Missed",
    description: "The expected execution window has passed without a new execution.",
    variantClass: "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20 hover:bg-amber-500/20",
    dotClass: "bg-amber-500 animate-pulse",
    icon: AlertTriangle,
  },
  STALLED: {
    label: "Stalled",
    description: "An execution has been running longer than the allowed runtime.",
    variantClass: "bg-destructive/10 text-destructive border-destructive/20 hover:bg-destructive/20",
    dotClass: "bg-destructive animate-pulse",
    icon: AlertCircle,
  },
  OVERDUE: {
    label: "Overdue",
    description: "A pending execution has remained queued longer than the configured limit.",
    variantClass: "bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/20 hover:bg-orange-500/20",
    dotClass: "bg-orange-500 animate-pulse",
    icon: Clock,
  },
  DISABLED: {
    label: "Disabled",
    description: "Reliability checks are disabled for this job.",
    variantClass: "bg-muted text-muted-foreground border-border hover:bg-muted/80",
    dotClass: "bg-muted-foreground",
    icon: ShieldOff,
  },
};

export function ReliabilityBadge({
  state,
  jobId,
  clickable = true,
  className,
  size = "default",
}: ReliabilityBadgeProps) {
  const config = STATE_CONFIG[state] || STATE_CONFIG.HEALTHY;

  const content = (
    <Badge
      variant="outline"
      title={`${config.label}: ${config.description}`}
      className={cn(
        "inline-flex items-center gap-1.5 transition-colors cursor-default font-medium",
        config.variantClass,
        size === "sm" && "text-[10px] px-1.5 py-0 h-4.5 gap-1",
        size === "default" && "text-xs px-2 py-0.5 h-5.5",
        size === "lg" && "text-sm px-3 py-1 h-7 gap-2 font-semibold",
        clickable && jobId && "cursor-pointer hover:opacity-90",
        className
      )}
    >
      <span className={cn("rounded-full shrink-0", config.dotClass, size === "lg" ? "h-2.5 w-2.5" : "h-1.5 w-1.5")} />
      <span>{config.label}</span>
    </Badge>
  );

  if (clickable && jobId) {
    return (
      <Link href={`/jobs/${jobId}/reliability`} className="inline-block transition-transform active:scale-95">
        {content}
      </Link>
    );
  }

  return content;
}
