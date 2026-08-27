import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { HeartPulseIcon, AlertTriangleIcon, XCircleIcon, InfoIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface HealthCardProps {
  health: "HEALTHY" | "DEGRADED" | "CRITICAL";
  title?: string;
  infoText?: string;
}

export function HealthCard({ health, title = "System Health", infoText }: HealthCardProps) {
  let bgColor = "bg-muted";
  let textColor = "text-muted-foreground";
  let Icon = HeartPulseIcon;
  let label = "Unknown";
  let subtitle = "Status overview";

  if (health === "HEALTHY") {
    bgColor = "bg-emerald-500/10";
    textColor = "text-emerald-600 dark:text-emerald-400";
    Icon = HeartPulseIcon;
    label = "Healthy";
    subtitle = "All systems operational";
  } else if (health === "DEGRADED") {
    bgColor = "bg-amber-500/10";
    textColor = "text-amber-600 dark:text-amber-400";
    Icon = AlertTriangleIcon;
    label = "Degraded";
    subtitle = "Elevated failures/retries";
  } else if (health === "CRITICAL") {
    bgColor = "bg-red-500/10";
    textColor = "text-red-600 dark:text-red-400";
    Icon = XCircleIcon;
    label = "Critical";
    subtitle = "Failure threshold breached";
  }

  return (
    <Card className={cn("overflow-hidden h-full flex flex-col justify-between", bgColor)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <CardTitle className={cn("text-sm font-medium truncate", textColor)}>{title}</CardTitle>
          {infoText && (
            <div title={infoText} className="cursor-help flex items-center shrink-0">
              <InfoIcon className={cn("h-3.5 w-3.5 hover:opacity-100 transition-opacity opacity-70", textColor)} />
            </div>
          )}
        </div>
        <Icon className={cn("h-4 w-4 shrink-0", textColor)} />
      </CardHeader>
      <CardContent className="pt-0">
        <div className={cn("text-2xl font-bold uppercase tracking-wider", textColor)}>
          {label}
        </div>
        <div className="mt-1 min-h-[1.25rem] flex items-center">
          <p className="text-xs text-muted-foreground truncate">{subtitle}</p>
        </div>
      </CardContent>
    </Card>
  );
}
