import { useQuery } from "@tanstack/react-query";
import { getJobAnalytics, getJobAnalyticsTrend, AnalyticsFilters } from "@/lib/api/analytics";

const STALE_TIME = 60 * 1000;

export function useJobAnalytics(jobId: number | null | undefined, filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["job-analytics", jobId, filters],
    queryFn: () => getJobAnalytics(jobId!, filters),
    enabled: !!jobId,
    staleTime: STALE_TIME,
  });
}

export function useJobAnalyticsTrend(jobId: number | null | undefined, filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["job-analytics-trend", jobId, filters],
    queryFn: () => getJobAnalyticsTrend(jobId!, filters),
    enabled: !!jobId,
    staleTime: STALE_TIME,
  });
}
