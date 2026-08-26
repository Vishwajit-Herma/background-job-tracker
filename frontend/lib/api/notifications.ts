import { apiClient } from "./client";

export interface NotificationChannel {
  id: number;
  project: number;
  type: "WEBHOOK" | "EMAIL";
  name: string;
  config: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationPolicy {
  id: number;
  project: number;
  channel: number;
  severity: "DEGRADED" | "CRITICAL";
  event_types: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InAppNotification {
  id: number;
  recipient: number;
  incident_event: number;
  title: string;
  message: string;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface PaginatedInAppNotifications {
  data: InAppNotification[];
  page: number;
  totalPages: number;
  totalItems: number;
}

export async function getInAppNotifications(
  page = 1,
  filters: { search?: string; ordering?: string } = {}
): Promise<PaginatedInAppNotifications> {
  const params = new URLSearchParams({ page: page.toString() });
  if (filters.search) params.append("search", filters.search);
  if (filters.ordering) params.append("ordering", filters.ordering);

  const res = await apiClient.get<any>(`/notifications/in-app/?${params.toString()}`);
  const payload = res.data;
  return {
    data: Array.isArray(payload.data) ? payload.data : Array.isArray(payload) ? payload : [],
    page: payload.page ?? 1,
    totalPages: payload.totalPages ?? 1,
    totalItems: payload.totalItems ?? 0,
  };
}

export async function getUnreadNotificationCount(): Promise<number> {
  try {
    const res = await apiClient.get<any>("/notifications/in-app/unread-count/");
    const count = res.data?.data?.unread_count ?? res.data?.unread_count ?? 0;
    return typeof count === "number" ? count : 0;
  } catch {
    return 0;
  }
}

export async function markNotificationAsRead(id: number): Promise<void> {
  await apiClient.post(`/notifications/in-app/${id}/read/`);
}

export async function markAllNotificationsAsRead(): Promise<void> {
  await apiClient.post("/notifications/in-app/read-all/");
}

export async function getNotificationChannels(
  projectId?: number,
  filters: { search?: string; ordering?: string } = {}
): Promise<NotificationChannel[]> {
  const params = new URLSearchParams({ no_pagination: "true" });
  if (projectId) params.append("project", projectId.toString());
  if (filters.search) params.append("search", filters.search);
  if (filters.ordering) params.append("ordering", filters.ordering);
  
  const res = await apiClient.get<any>(`/notifications/channels/?${params.toString()}`);
  return Array.isArray(res.data?.data) ? res.data.data : Array.isArray(res.data) ? res.data : [];
}

export async function createNotificationChannel(payload: Partial<NotificationChannel>): Promise<NotificationChannel> {
  const res = await apiClient.post<any>("/notifications/channels/", payload);
  return res.data?.data ?? res.data;
}

export async function updateNotificationChannel(id: number, payload: Partial<NotificationChannel>): Promise<NotificationChannel> {
  const res = await apiClient.patch<any>(`/notifications/channels/${id}/`, payload);
  return res.data?.data ?? res.data;
}

export async function deleteNotificationChannel(id: number): Promise<void> {
  await apiClient.delete(`/notifications/channels/${id}/`);
}

export async function getNotificationPolicies(
  projectId?: number,
  filters: { search?: string; ordering?: string } = {}
): Promise<NotificationPolicy[]> {
  const params = new URLSearchParams({ no_pagination: "true" });
  if (projectId) params.append("project", projectId.toString());
  if (filters.search) params.append("search", filters.search);
  if (filters.ordering) params.append("ordering", filters.ordering);
  
  const res = await apiClient.get<any>(`/notifications/policies/?${params.toString()}`);
  return res.data?.data ?? res.data ?? [];
}

export interface PaginatedChannels {
  data: NotificationChannel[];
  page: number;
  totalPages: number;
  totalItems: number;
}

export async function getPaginatedNotificationChannels(
  page = 1,
  filters: { search?: string; ordering?: string } = {}
): Promise<PaginatedChannels> {
  const params = new URLSearchParams({ page: page.toString() });
  if (filters.search) params.append("search", filters.search);
  if (filters.ordering) params.append("ordering", filters.ordering);
  
  const res = await apiClient.get<any>(`/notifications/channels/?${params.toString()}`);
  const payload = res.data;
  return {
    data: Array.isArray(payload.data) ? payload.data : Array.isArray(payload) ? payload : [],
    page: payload.page ?? 1,
    totalPages: payload.totalPages ?? 1,
    totalItems: payload.totalItems ?? 0,
  };
}

export interface PaginatedPolicies {
  data: NotificationPolicy[];
  page: number;
  totalPages: number;
  totalItems: number;
}

export async function getPaginatedNotificationPolicies(
  page = 1,
  filters: { search?: string; ordering?: string } = {}
): Promise<PaginatedPolicies> {
  const params = new URLSearchParams({ page: page.toString() });
  if (filters.search) params.append("search", filters.search);
  if (filters.ordering) params.append("ordering", filters.ordering);
  
  const res = await apiClient.get<any>(`/notifications/policies/?${params.toString()}`);
  const payload = res.data;
  return {
    data: Array.isArray(payload.data) ? payload.data : Array.isArray(payload) ? payload : [],
    page: payload.page ?? 1,
    totalPages: payload.totalPages ?? 1,
    totalItems: payload.totalItems ?? 0,
  };
}

export async function createNotificationPolicy(payload: Partial<NotificationPolicy>): Promise<NotificationPolicy> {
  const res = await apiClient.post<any>("/notifications/policies/", payload);
  return res.data?.data ?? res.data;
}

export async function updateNotificationPolicy(id: number, payload: Partial<NotificationPolicy>): Promise<NotificationPolicy> {
  const res = await apiClient.patch<any>(`/notifications/policies/${id}/`, payload);
  return res.data?.data ?? res.data;
}

export async function deleteNotificationPolicy(id: number): Promise<void> {
  await apiClient.delete(`/notifications/policies/${id}/`);
}
