import { apiClient } from "./client";
import { User } from "./auth";

export interface Team {
  id: number;
  name: string;
  slug: string;
  description: string;
  owner: number;
  my_role: "owner" | "admin" | "member" | "staff" | null;
  created_at: string;
  updated_at: string;
}

export interface TeamMember {
  id: number;
  team: number;
  user: User;
  role: "owner" | "admin" | "member";
  is_active: boolean;
  joined_at: string;
}

export async function getTeams(params: { search?: string; ordering?: string } = {}): Promise<Team[]> {
  const query = new URLSearchParams({ no_pagination: "true" });
  if (params.search) query.append("search", params.search);
  if (params.ordering) query.append("ordering", params.ordering);
  
  const { data } = await apiClient.get<{ data: Team[] }>(`/teams/?${query.toString()}`);
  return data.data || (data as any);
}

export async function getTeamMembers(teamId: number, params: { search?: string; ordering?: string } = {}): Promise<TeamMember[]> {
  const query = new URLSearchParams({ no_pagination: "true" });
  if (params.search) query.append("search", params.search);
  if (params.ordering) query.append("ordering", params.ordering);

  const { data } = await apiClient.get<{ data: TeamMember[] }>(`/teams/${teamId}/members/?${query.toString()}`);
  return data.data || (data as any);
}

export async function createTeam(payload: { name: string; description?: string }): Promise<Team> {
  const { data } = await apiClient.post<{ data: Team }>("/teams/", payload);
  // POST usually returns the object directly if created without pagination, 
  // but let's check if there's a custom renderer. For now, assuming POST returns object directly or `{ data: object }`.
  // Actually, Keel's custom viewset might just return the object. Let's return data.data if it exists, otherwise data.
  return (data as any).data || data;
}

export async function updateTeam(teamId: number, payload: { name: string; description?: string }): Promise<Team> {
  const { data } = await apiClient.patch<{ data: Team }>(`/teams/${teamId}/`, payload);
  return (data as any).data || data;
}

export async function deleteTeam(teamId: number): Promise<void> {
  await apiClient.delete(`/teams/${teamId}/`);
}

export async function updateTeamMemberRole(teamId: number, memberId: number, role: string): Promise<TeamMember> {
  const { data } = await apiClient.patch<{ data: TeamMember }>(`/teams/${teamId}/members/${memberId}/`, { role });
  return (data as any).data || data;
}

export async function removeTeamMember(teamId: number, memberId: number): Promise<void> {
  await apiClient.delete(`/teams/${teamId}/members/${memberId}/`);
}

export interface TeamInvitation {
  id: number;
  team: number;
  team_name: string;
  email: string;
  role: "owner" | "admin" | "member";
  status: string;
  invited_by: number;
  invited_by_email: string;
  created_at: string;
  expires_at: string;
}

export async function getInvitations(teamId: number): Promise<TeamInvitation[]> {
  const { data } = await apiClient.get<{ data: TeamInvitation[] }>(`/teams/${teamId}/invitations/`);
  return data.data;
}

export async function inviteUser(teamId: number, email: string, role: string): Promise<TeamInvitation> {
  const { data } = await apiClient.post<{ data: TeamInvitation }>(`/teams/${teamId}/invitations/`, { email, role });
  return (data as any).data || data;
}

export async function getMyInvitations(): Promise<TeamInvitation[]> {
  const { data } = await apiClient.get<{ data: TeamInvitation[] }>("/teams/my-invitations/");
  return data.data || [];
}

export async function acceptInvitation(invitationId: number): Promise<void> {
  await apiClient.post(`/teams/my-invitations/${invitationId}/accept/`);
}

export async function declineInvitation(invitationId: number): Promise<void> {
  await apiClient.post(`/teams/my-invitations/${invitationId}/decline/`);
}
