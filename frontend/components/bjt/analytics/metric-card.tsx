import { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowDownIcon, ArrowUpIcon, InfoIcon, LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon?: LucideIcon;
  infoText?: string;
  trend?: {
    value: number | string;
    label?: string;
    direction: "up" | "down" | "neutral";
    isFavorable: boolean;
    tooltip?: string;
  };
  valueClassName?: string;
}

export function MetricCard({ title, value, icon: Icon, infoText, trend, valueClassName }: MetricCardProps) {
  return (
    <Card className="h-full flex flex-col justify-between">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <CardTitle className="text-sm font-medium truncate">{title}</CardTitle>
          {infoText && (
            <div title={infoText} className="cursor-help flex items-center shrink-0">
              <InfoIcon className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors" />
            </div>
          )}
        </div>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground shrink-0" />}
      </CardHeader>
      <CardContent className="pt-0">
        <div className={cn("text-2xl font-bold tracking-tight", valueClassName)}>{value}</div>
        <div className="mt-1 min-h-[1.25rem] flex items-center" title={trend?.tooltip}>
          {trend ? (
            <p className="text-xs text-muted-foreground flex items-center truncate">
              {trend.direction === "up" && (
                <ArrowUpIcon
                  className={cn(
                    "mr-1 h-3 w-3 shrink-0",
                    trend.isFavorable ? "text-emerald-500" : "text-destructive"
                  )}
                />
              )}
              {trend.direction === "down" && (
                <ArrowDownIcon
                  className={cn(
                    "mr-1 h-3 w-3 shrink-0",
                    trend.isFavorable ? "text-emerald-500" : "text-destructive"
                  )}
                />
              )}
              {trend.value ? (
                <span
                  className={cn(
                    "mr-1 shrink-0",
                    trend.direction !== "neutral" &&
                      (trend.isFavorable ? "text-emerald-500" : "text-destructive")
                  )}
                >
                  {trend.value}
                </span>
              ) : null}
              {trend.label && <span className="truncate">{trend.label}</span>}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground opacity-0 select-none">—</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
