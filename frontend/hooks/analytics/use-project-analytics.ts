import { useQuery } from "@tanstack/react-query";
import { getProjectAnalytics, getProjectAnalyticsTrend, AnalyticsFilters } from "@/lib/api/analytics";

// 1 minute stale time so we don't aggressively poll but it refreshes naturally
const STALE_TIME = 60 * 1000;

export function useProjectAnalytics(projectId: number | null | undefined, filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["project-analytics", projectId, filters],
    queryFn: () => getProjectAnalytics(projectId!, filters),
    enabled: !!projectId,
    staleTime: STALE_TIME,
  });
}

export function useProjectAnalyticsTrend(projectId: number | null | undefined, filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["project-analytics-trend", projectId, filters],
    queryFn: () => getProjectAnalyticsTrend(projectId!, filters),
    enabled: !!projectId,
    staleTime: STALE_TIME,
  });
}
