"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { getWebSocketUrl, RealtimeEvent } from "@/lib/api/realtime";
import { toastInfo } from "@/lib/toast";

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

interface RealtimeContextValue {
  status: ConnectionStatus;
  lastEvent: RealtimeEvent | null;
  reconnect: () => void;
}

const RealtimeContext = createContext<RealtimeContextValue>({
  status: "disconnected",
  lastEvent: null,
  reconnect: () => {},
});

export const useRealtime = () => useContext(RealtimeContext);

const PING_INTERVAL_MS = 30000;
const ANALYTICS_DEBOUNCE_MS = 5000;

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const analyticsDebounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const retryCountRef = useRef<number>(0);
  const hasConnectedOnceRef = useRef<boolean>(false);
  const isUnmountedRef = useRef<boolean>(false);

  // Debounced refetch for expensive PostgreSQL analytics
  const scheduleAnalyticsRefetch = useCallback(
    (projectId?: number, jobIds?: number[]) => {
      if (analyticsDebounceTimerRef.current) {
        clearTimeout(analyticsDebounceTimerRef.current);
      }

      analyticsDebounceTimerRef.current = setTimeout(() => {
        if (projectId) {
          queryClient.invalidateQueries({
            queryKey: ["project-analytics", projectId],
            refetchType: "active",
          });
          queryClient.invalidateQueries({
            queryKey: ["project-analytics-trend", projectId],
            refetchType: "active",
          });
        }
        if (jobIds && jobIds.length > 0) {
          for (const jobId of jobIds) {
            queryClient.invalidateQueries({
              queryKey: ["job-analytics", jobId],
              refetchType: "active",
            });
            queryClient.invalidateQueries({
              queryKey: ["job-analytics-trend", jobId],
              refetchType: "active",
            });
          }
        }
      }, ANALYTICS_DEBOUNCE_MS);
    },
    [queryClient]
  );

  // Handle incoming realtime event with targeted invalidations
  const handleRealtimeEvent = useCallback(
    (event: RealtimeEvent) => {
      setLastEvent(event);

      switch (event.type) {
        case "execution.batch": {
          const projectId = event.project_id as number | undefined;
          const jobIds = (event.job_ids as number[]) || [];

          // Targeted invalidation for executions list
          queryClient.invalidateQueries({ queryKey: ["executions-all"] });
          if (projectId) {
            queryClient.invalidateQueries({ queryKey: ["executions", projectId] });
          }

          // Targeted invalidation only for affected jobs
          if (jobIds.length > 0) {
            for (const jId of jobIds) {
              queryClient.invalidateQueries({ queryKey: ["job", jId] });
            }
            queryClient.invalidateQueries({ queryKey: ["jobs"] });
          }

          // Protect database: debounce heavy analytics aggregations
          scheduleAnalyticsRefetch(projectId, jobIds);
          break;
        }

        case "incident.updated": {
          const incidentId = event.incident_id as number | undefined;
          const projectId = event.project_id as number | undefined;
          const newStatus = event.status as string | undefined;

          // Optimistically update single incident cache
          if (incidentId && newStatus) {
            queryClient.setQueryData(["incident", incidentId], (old: any) =>
              old ? { ...old, status: newStatus } : old
            );
          }

          // Optimistically update incident lists in cache
          if (incidentId && newStatus) {
            queryClient.setQueriesData({ queryKey: ["incidents"] }, (old: any) => {
              if (!old) return old;
              if (Array.isArray(old)) {
                return old.map((inc: any) => (inc.id === incidentId ? { ...inc, status: newStatus } : inc));
              }
              if (old.data && Array.isArray(old.data)) {
                return {
                  ...old,
                  data: old.data.map((inc: any) => (inc.id === incidentId ? { ...inc, status: newStatus } : inc)),
                };
              }
              return old;
            });
          }

          if (incidentId) {
            queryClient.invalidateQueries({ queryKey: ["incident", incidentId] });
            queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
          }
          if (projectId) {
            queryClient.invalidateQueries({ queryKey: ["incidents", projectId] });
          }
          queryClient.invalidateQueries({ queryKey: ["incidents"] });
          break;
        }

        case "incident.note.created": {
          // Strictly deduplicated: does NOT trigger general incident list refetches
          const incidentId = event.incident_id as number | undefined;
          if (incidentId) {
            queryClient.invalidateQueries({ queryKey: ["incident-notes", incidentId] });
            queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
          }
          break;
        }

        case "incident.intelligence.updated": {
          const incidentId = event.incident_id as number | undefined;
          if (incidentId) {
            queryClient.invalidateQueries({ queryKey: ["incident-intelligence", incidentId] });
            queryClient.invalidateQueries({ queryKey: ["incident", incidentId] });
          }
          break;
        }

        case "runbook.updated":
        case "runbook.execution.updated": {
          const incidentId = event.incident_id as number | undefined;
          if (incidentId) {
            queryClient.invalidateQueries({ queryKey: ["runbooks", incidentId] });
            queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
          }
          break;
        }

        case "postmortem.updated":
        case "postmortem.action_item.updated": {
          const incidentId = event.incident_id as number | undefined;
          if (incidentId) {
            queryClient.invalidateQueries({ queryKey: ["postmortem", incidentId] });
            queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
          }
          break;
        }

        case "notification.created": {
          // Optimistically increment unread badge immediately
          queryClient.setQueryData<number>(["notifications-unread-count"], (old) => (old ?? 0) + 1);

          // Optimistically prepend incoming notification into preview and list caches
          if (event.id || event.title) {
            const newNotif = {
              id: (event.id as number) || Date.now(),
              title: (event.title as string) || "Notification",
              message: (event.message as string) || "",
              incident_id: event.incident_id as number | undefined,
              event_type: event.event_type as string | undefined,
              incident_severity: event.incident_severity as string | undefined,
              project_name: event.project_name as string | undefined,
              job_name: event.job_name as string | undefined,
              is_read: false,
              created_at: (event.created_at as string) || new Date().toISOString(),
            };

            queryClient.setQueryData(["notifications-preview"], (old: any) => {
              if (!old) return { data: [newNotif], totalItems: 1, totalPages: 1 };
              const existing = old.data || [];
              if (existing.some((n: any) => n.id === newNotif.id)) return old;
              return {
                ...old,
                data: [newNotif, ...existing].slice(0, 10),
                totalItems: (old.totalItems || 0) + 1,
              };
            });

            queryClient.setQueriesData({ queryKey: ["notifications"] }, (old: any) => {
              if (!old) return old;
              if (Array.isArray(old)) {
                if (old.some((n: any) => n.id === newNotif.id)) return old;
                return [newNotif, ...old];
              }
              if (old.data && Array.isArray(old.data)) {
                if (old.data.some((n: any) => n.id === newNotif.id)) return old;
                return {
                  ...old,
                  data: [newNotif, ...old.data],
                  totalItems: (old.totalItems || 0) + 1,
                };
              }
              return old;
            });
          }

          queryClient.invalidateQueries({ queryKey: ["notifications"] });
          queryClient.invalidateQueries({ queryKey: ["notifications-preview"] });
          queryClient.invalidateQueries({ queryKey: ["notifications-unread-count"] });

          if (event.title && typeof event.title === "string") {
            toastInfo("Notification", event.title);
          }
          break;
        }

        case "notification.updated": {
          queryClient.invalidateQueries({ queryKey: ["notifications"] });
          queryClient.invalidateQueries({ queryKey: ["notifications-preview"] });
          queryClient.invalidateQueries({ queryKey: ["notifications-unread-count"] });
          break;
        }

        case "reliability.finding.updated": {
          const projectId = event.project_id as number | undefined;
          if (projectId) {
            queryClient.invalidateQueries({ queryKey: ["reliability-findings", projectId] });
          }
          queryClient.invalidateQueries({ queryKey: ["job-expectations"] });
          break;
        }

        case "baseline.updated": {
          const jobId = event.job_id as number | undefined;
          if (jobId) {
            queryClient.invalidateQueries({ queryKey: ["job-baseline", jobId] });
          }
          break;
        }

        case "job.updated": {
          const jobId = event.job_id as number | undefined;
          if (jobId) {
            queryClient.invalidateQueries({ queryKey: ["job", jobId] });
          }
          queryClient.invalidateQueries({ queryKey: ["jobs"] });
          break;
        }

        case "project.updated": {
          const projectId = event.project_id as number | undefined;
          if (projectId) {
            queryClient.invalidateQueries({ queryKey: ["project", projectId] });
          }
          queryClient.invalidateQueries({ queryKey: ["projects"] });
          break;
        }

        case "alert_rule.updated": {
          queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
          break;
        }

        case "team.updated":
        case "team.member.updated": {
          const teamId = event.team_id as number | undefined;
          if (teamId) {
            queryClient.invalidateQueries({ queryKey: ["team-members", teamId] });
          }
          queryClient.invalidateQueries({ queryKey: ["teams"] });
          break;
        }

        default:
          break;
      }
    },
    [queryClient, scheduleAnalyticsRefetch]
  );

  // Synchronize state after a temporary WebSocket disconnection
  const performReconnectResync = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["notifications-unread-count"] });
    queryClient.invalidateQueries({ queryKey: ["incidents"] });
    queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
  }, [queryClient]);

  // Establish WebSocket connection
  const connect = useCallback(async () => {
    if (isUnmountedRef.current || !user) return;

    // Clean up existing socket if any
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    setStatus("connecting");

    try {
      const url = await getWebSocketUrl();
      if (isUnmountedRef.current) return;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isUnmountedRef.current) return;
        setStatus("connected");
        const wasReconnecting = hasConnectedOnceRef.current;
        hasConnectedOnceRef.current = true;
        retryCountRef.current = 0;

        // If reconnecting after a dropped connection, catch up on missed state
        if (wasReconnecting) {
          performReconnectResync();
        }

        // Setup periodic heartbeat ping
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "ping" }));
          }
        }, PING_INTERVAL_MS);
      };

      ws.onmessage = (messageEvent) => {
        try {
          const data = JSON.parse(messageEvent.data);
          if (data.action === "pong") return;
          if (data.type === "connection.ready" || data.type === "scopes.resynced") return;
          handleRealtimeEvent(data);
        } catch (err) {
          console.warn("Failed to parse realtime message:", err);
        }
      };

      ws.onerror = () => {
        setStatus("error");
      };

      ws.onclose = (closeEvent) => {
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        if (isUnmountedRef.current) return;

        setStatus("disconnected");

        // Custom code 4001 indicates unauthorized user, do not loop reconnect
        if (closeEvent.code === 4001) {
          console.warn("WebSocket closed due to unauthenticated session (4001).");
          return;
        }

        // Normal closure (e.g. intentional logout or re-auth)
        if (closeEvent.code === 1000) {
          return;
        }

        // Reconnect with exponential backoff + jitter
        const backoffDelay = Math.min(
          1000 * Math.pow(1.5, retryCountRef.current),
          30000
        ) + Math.random() * 500;

        retryCountRef.current += 1;

        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, backoffDelay);
      };
    } catch (err) {
      console.warn("Error initializing WebSocket connection:", err);
      setStatus("error");
      const backoffDelay = Math.min(
        1000 * Math.pow(1.5, retryCountRef.current),
        30000
      ) + Math.random() * 500;
      retryCountRef.current += 1;
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, backoffDelay);
    }
  }, [user, handleRealtimeEvent, performReconnectResync]);

  useEffect(() => {
    isUnmountedRef.current = false;

    if (user) {
      connect();
    } else {
      // If user logs out, disconnect immediately
      if (wsRef.current) {
        wsRef.current.close(1000, "User logged out");
        wsRef.current = null;
      }
      setStatus("disconnected");
      hasConnectedOnceRef.current = false;
    }

    return () => {
      isUnmountedRef.current = true;
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (analyticsDebounceTimerRef.current) clearTimeout(analyticsDebounceTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.close(1000, "Component unmounting");
        wsRef.current = null;
      }
    };
  }, [user, connect]);

  return (
    <RealtimeContext.Provider
      value={{
        status,
        lastEvent,
        reconnect: connect,
      }}
    >
      {children}
    </RealtimeContext.Provider>
  );
}
