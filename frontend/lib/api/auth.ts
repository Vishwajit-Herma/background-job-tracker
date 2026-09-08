import { apiClient } from "./client";

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_staff: boolean;
  avatar_url?: string;
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const { data } = await apiClient.get<any>("/auth/user/");
    if (data && data.pk) {
      data.id = data.pk;
    }
    return data as User;
  } catch (error: unknown) {
    const err = error as { status?: number };
    if (err.status === 401 || err.status === 403) {
      return null;
    }
    throw error;
  }
}

export async function login(credentials: Record<string, string>): Promise<void> {
  await apiClient.post("/auth/login/", credentials);
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout/");
}

export async function register(credentials: Record<string, string>): Promise<User> {
  const { data } = await apiClient.post<User>("/auth/registration/", credentials);
  return data;
}

export async function verifyEmail(key: string): Promise<void> {
  await apiClient.post("/auth/registration/verify-email/", { key });
}

export async function resetPassword(email: string): Promise<void> {
  await apiClient.post("/auth/password/reset/", { email });
}

export async function resetPasswordConfirm(data: Record<string, string>): Promise<void> {
  await apiClient.post("/auth/password/reset/confirm/", data);
}

export async function updateUser(data: Partial<User>): Promise<User> {
  const response = await apiClient.patch<User>("/auth/user/", data);
  return response.data;
}
