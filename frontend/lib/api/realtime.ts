import { apiClient } from "./client";

export interface RealtimeTicketResponse {
  ticket: string;
  expires_in: number;
}

export interface RealtimeEvent {
  type: string;
  timestamp: string;
  project_id?: number;
  team_id?: number;
  user_id?: number;
  [key: string]: unknown;
}

export interface ExecutionBatchPayload extends RealtimeEvent {
  type: "execution.batch";
  count: number;
  job_ids: number[];
  statuses?: string[];
}

export interface IncidentUpdatedPayload extends RealtimeEvent {
  type: "incident.updated";
  incident_id: number;
  status: string;
  event_type: string;
}

export interface IncidentNoteCreatedPayload extends RealtimeEvent {
  type: "incident.note.created";
  incident_id: number;
  event_id: number;
}

/**
 * Request a short-lived (60s), single-use ticket for authenticating the
 * WebSocket connection across cross-origin deployments (e.g. Vercel to Render).
 */
export async function getWebSocketTicket(): Promise<string> {
  const response = await apiClient.post<RealtimeTicketResponse>("/realtime/ticket/");
  return response.data.ticket;
}

/**
 * Determine the WebSocket server base URL based on environment configuration.
 */
export function getWebSocketBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL.replace(/\/+$/, "");
  }

  const rawApiUrl =
    process.env.NEXT_PUBLIC_DJANGO_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.DJANGO_API_URL;

  if (rawApiUrl) {
    let apiUrl = rawApiUrl.replace(/\/+$/, "");
    if (apiUrl.endsWith("/api")) {
      apiUrl = apiUrl.slice(0, -4);
    }
    return apiUrl.replace(/^http/, "ws");
  }
  if (typeof window !== "undefined") {
    // If local dev on port 3000, default Django backend is on port 8000
    if (window.location.port === "3000") {
      return `ws://${window.location.hostname}:8000`;
    }
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }
  return "ws://localhost:8000";
}

/**
 * Build the full authenticated WebSocket URL with a fresh single-use ticket.
 */
export async function getWebSocketUrl(): Promise<string> {
  const baseUrl = getWebSocketBaseUrl();
  try {
    const ticket = await getWebSocketTicket();
    return `${baseUrl}/ws/realtime/?ticket=${encodeURIComponent(ticket)}`;
  } catch (err) {
    console.warn("Failed to retrieve WebSocket ticket; attempting fallback handshake:", err);
    return `${baseUrl}/ws/realtime/`;
  }
}
