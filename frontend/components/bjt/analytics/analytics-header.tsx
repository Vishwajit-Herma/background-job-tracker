"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { RefreshCwIcon } from "lucide-react";
import { useWorkspace } from "@/hooks/use-workspace";
import { useCallback } from "react";

interface AnalyticsHeaderProps {
  title: string;
  showProjectFilter?: boolean;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

const RANGE_OPTIONS = [
  { value: "1h", label: "Last 1 Hour" },
  { value: "6h", label: "Last 6 Hours" },
  { value: "24h", label: "Last 24 Hours" },
  { value: "7d", label: "Last 7 Days" },
  { value: "30d", label: "Last 30 Days" },
];

export function AnalyticsHeader({
  title,
  showProjectFilter = false,
  onRefresh,
  isRefreshing = false,
}: AnalyticsHeaderProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { projects } = useWorkspace();

  const rawRange = searchParams.get("range") || "24h";
  const currentRange =
    rawRange === "last_1_hour"
      ? "1h"
      : rawRange === "last_6_hours"
      ? "6h"
      : rawRange === "last_24_hours"
      ? "24h"
      : rawRange === "last_7_days"
      ? "7d"
      : rawRange === "last_30_days"
      ? "30d"
      : rawRange;
  const currentProject = searchParams.get("project") || "";

  const createQueryString = useCallback(
    (name: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) {
        params.set(name, value);
      } else {
        params.delete(name);
      }
      return params.toString();
    },
    [searchParams]
  );

  const handleRangeChange = (value: string | null) => {
    if (value) {
      router.push(pathname + "?" + createQueryString("range", value));
    }
  };

  const handleProjectChange = (value: string | null) => {
    if (value) {
      router.push(pathname + "?" + createQueryString("project", value === "all" ? "" : value));
    }
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Overview of your background job reliability and performance.
        </p>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {showProjectFilter && (
          <Select value={currentProject || (projects.length > 0 ? projects[0].id.toString() : "")} onValueChange={handleProjectChange}>
            <SelectTrigger className="w-[200px]">
              <span data-slot="select-value" className="flex flex-1 text-left line-clamp-1">
                {currentProject
                  ? projects.find((p) => p.id.toString() === currentProject)?.name
                  : (projects.length > 0 ? projects[0].name : "Select Project")}
              </span>
            </SelectTrigger>
            <SelectContent>
              {projects.map((p) => (
                <SelectItem key={p.id} value={p.id.toString()}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <Select value={currentRange} onValueChange={handleRangeChange}>
          <SelectTrigger className="w-[160px]">
            <span data-slot="select-value" className="flex flex-1 text-left line-clamp-1">
              {RANGE_OPTIONS.find((opt) => opt.value === currentRange)?.label || "Select range"}
            </span>
          </SelectTrigger>
          <SelectContent>
            {RANGE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          size="icon"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh Data"
        >
          <RefreshCwIcon className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
        </Button>
      </div>
    </div>
  );
}
