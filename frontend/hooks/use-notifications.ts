"use client";

import { useQuery } from "@tanstack/react-query";
import { getUnreadNotificationCount } from "@/lib/api/notifications";

/**
 * Production-ready custom hook for tracking unread notification count.
 *
 * - Disables automatic polling (refetchInterval: false) and relies on WebSockets
 *   ("notification.created", "notification.updated") & optimistic updates as the
 *   realtime driver.
 * - REST query remains the single authoritative source of truth.
 */
export function useUnreadNotificationCount() {
  return useQuery({
    queryKey: ["notifications-unread-count"],
    queryFn: getUnreadNotificationCount,
    refetchInterval: false,
    staleTime: Infinity,
  });
}
