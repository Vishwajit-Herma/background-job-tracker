"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTeam } from "@/components/bjt/team-provider";
import { useAuth } from "@/hooks/use-auth";
import { 
  getTeamMembers, 
  removeTeamMember, 
  updateTeamMemberRole, 
  getMyInvitations, 
  acceptInvitation, 
  declineInvitation 
} from "@/lib/api/teams";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger 
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/bjt/states";
import { Users, UserPlus, Check, X, ChevronDown, Loader2, ShieldAlert, Mail } from "lucide-react";
import { InviteMemberModal } from "@/components/bjt/invite-member-modal";
import { TeamSettingsTab } from "@/components/bjt/team-settings-tab";
import { TeamInvitationsTab } from "@/components/bjt/team-invitations-tab";

export default function TeamPage() {
  const { user } = useAuth();
  const { teams, activeTeam, setActiveTeam } = useTeam();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"members" | "invitations" | "settings">("members");
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [changingRoleId, setChangingRoleId] = useState<number | null>(null);
  const [acceptingId, setAcceptingId] = useState<number | null>(null);
  const [decliningId, setDecliningId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: members = [], isLoading: isLoadingMembers } = useQuery({
    queryKey: ["team-members", activeTeam?.id],
    queryFn: () => getTeamMembers(activeTeam!.id),
    enabled: !!activeTeam,
  });

  const { data: myInvitations = [], isLoading: isLoadingInvites } = useQuery({
    queryKey: ["my-invitations"],
    queryFn: getMyInvitations,
  });

  // Determine current user's role in the active team
  const currentMember = members.find((m) => m.user.email === user?.email);
  const isOwner = currentMember?.role === "owner";
  const isAdmin = currentMember?.role === "admin";
  
  // They can manage if they are admin/owner OR they are a global staff admin
  const canManage = isOwner || isAdmin || user?.is_staff;

  const handleRemoveMember = async (memberId: number) => {
    if (!activeTeam) return;
    setActionError(null);
    setRemovingId(memberId);
    try {
      await removeTeamMember(activeTeam.id, memberId);
      queryClient.invalidateQueries({ queryKey: ["team-members", activeTeam.id] });
    } catch (e: any) {
      setActionError(e?.message || "Failed to remove member. You may not have permission.");
    } finally {
      setRemovingId(null);
    }
  };

  const handleChangeRole = async (memberId: number, newRole: string) => {
    if (!activeTeam) return;
    setActionError(null);
    setChangingRoleId(memberId);
    try {
      await updateTeamMemberRole(activeTeam.id, memberId, newRole);
      queryClient.invalidateQueries({ queryKey: ["team-members", activeTeam.id] });
    } catch (e: any) {
      setActionError(e?.message || "Failed to update role.");
    } finally {
      setChangingRoleId(null);
    }
  };

  const handleAcceptInvite = async (invitationId: number) => {
    setAcceptingId(invitationId);
    setActionError(null);
    try {
      await acceptInvitation(invitationId);
      // Invalidate both invitations and teams list to reflect new membership
      queryClient.invalidateQueries({ queryKey: ["my-invitations"] });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
    } catch (e: any) {
      setActionError(e?.message || "Failed to accept invitation");
    } finally {
      setAcceptingId(null);
    }
  };

  const handleDeclineInvite = async (invitationId: number) => {
    setDecliningId(invitationId);
    setActionError(null);
    try {
      await declineInvitation(invitationId);
      queryClient.invalidateQueries({ queryKey: ["my-invitations"] });
    } catch (e: any) {
      setActionError(e?.message || "Failed to decline invitation");
    } finally {
      setDecliningId(null);
    }
  };

  const roleBadgeVariant = (role: string) => {
    if (role === "owner") return "default";
    if (role === "admin") return "secondary";
    return "outline";
  };

  const pendingInvitationsBlock = myInvitations.length > 0 && (
    <div className="mb-6 rounded-lg border border-yellow-200 bg-yellow-50/50 dark:border-yellow-900/40 dark:bg-yellow-900/10 p-5">
      <div className="flex items-center gap-2 mb-4">
        <Mail className="h-5 w-5 text-yellow-600 dark:text-yellow-500" />
        <h3 className="text-base font-semibold text-yellow-900 dark:text-yellow-300">
          Pending Invitations ({myInvitations.length})
        </h3>
      </div>
      <div className="rounded-md border bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Team</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Invited By</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {myInvitations.map((invite) => (
              <TableRow key={invite.id}>
                <TableCell className="font-medium">{invite.team_name}</TableCell>
                <TableCell>
                  <Badge variant={roleBadgeVariant(invite.role)}>{invite.role.toUpperCase()}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground text-sm">{invite.invited_by_email}</TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="text-green-600 hover:text-green-700 hover:bg-green-100 dark:hover:bg-green-900/30"
                      onClick={() => handleAcceptInvite(invite.id)}
                      disabled={acceptingId === invite.id || decliningId === invite.id}
                    >
                      {acceptingId === invite.id ? (
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      ) : (
                        <Check className="h-4 w-4 mr-1" />
                      )}
                      Accept
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="text-destructive hover:text-destructive hover:bg-destructive/10"
                      onClick={() => handleDeclineInvite(invite.id)}
                      disabled={acceptingId === invite.id || decliningId === invite.id}
                    >
                      {decliningId === invite.id ? (
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      ) : (
                        <X className="h-4 w-4 mr-1" />
                      )}
                      Decline
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );

  if (teams.length === 0) {
    return (
      <div className="flex-1 space-y-6 p-8 pt-6">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Teams</h2>
          <p className="text-muted-foreground mt-1">Manage your team memberships and invitations.</p>
        </div>

        {isLoadingInvites ? (
          <div className="flex items-center gap-2 text-muted-foreground py-4">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Loading invitations...</span>
          </div>
        ) : (
          pendingInvitationsBlock
        )}

        <EmptyState 
          title="No team yet"
          description="You don't belong to any team yet. Accept an invitation above, or ask an admin to create one for you."
          icon={<Users className="h-10 w-10 text-muted-foreground" />}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 p-8 pt-6 space-y-6">
      {/* Pending invitations banner */}
      {!isLoadingInvites && pendingInvitationsBlock}

      {/* Action error banner */}
      {actionError && (
        <div className="flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="ml-auto">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[240px_1fr]">
        {/* ── Team Switcher Sidebar ── */}
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-wide font-semibold text-muted-foreground px-2 mb-2">
            Your Teams
          </p>
          {teams.map((team) => (
            <button
              key={team.id}
              onClick={() => setActiveTeam(team)}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors flex items-center justify-between gap-2 ${
                activeTeam?.id === team.id
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div
                  className={`h-2 w-2 rounded-full shrink-0 ${
                    activeTeam?.id === team.id ? "bg-primary" : "bg-muted-foreground/40"
                  }`}
                />
                <span className="truncate">{team.name}</span>
              </div>
              {team.my_role && (
                <span className="text-xs opacity-50 shrink-0 capitalize">{team.my_role}</span>
              )}
            </button>
          ))}
        </div>

        {/* ── Team Detail Panel ── */}
        {activeTeam ? (
          <div className="space-y-6 min-w-0">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold tracking-tight">{activeTeam.name}</h2>
                <p className="text-muted-foreground mt-1 text-sm">
                  Manage members, invitations and settings for this team.
                </p>
              </div>
              {canManage && activeTab !== "settings" && (
                <Button onClick={() => setIsInviteModalOpen(true)}>
                  <UserPlus className="mr-2 h-4 w-4" />
                  Invite Member
                </Button>
              )}
            </div>

            {/* Tab bar */}
            <div className="flex space-x-1 border-b">
              {(["members", ...(canManage ? ["invitations", "settings"] : [])] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab as any)}
                  className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
                    activeTab === tab
                      ? "border-primary text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Members tab */}
            {activeTab === "members" && (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Joined</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {isLoadingMembers ? (
                      <TableRow>
                        <TableCell colSpan={5} className="h-24 text-center">
                          <Loader2 className="h-5 w-5 animate-spin mx-auto text-muted-foreground" />
                        </TableCell>
                      </TableRow>
                    ) : members.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                          No members found.
                        </TableCell>
                      </TableRow>
                    ) : (
                      members.map((member) => {
                        const isSelf = member.user.email === user?.email;
                        const isChangingThisRole = changingRoleId === member.id;
                        const isRemovingThis = removingId === member.id;
                        return (
                          <TableRow key={member.id}>
                            <TableCell className="font-medium">
                              <div className="flex items-center gap-2">
                                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold text-primary">
                                  {(member.user.first_name?.[0] || member.user.email[0]).toUpperCase()}
                                </div>
                                <div>
                                  <div className="flex items-center gap-1">
                                    {member.user.first_name || member.user.last_name
                                      ? `${member.user.first_name} ${member.user.last_name}`.trim()
                                      : <span className="text-muted-foreground italic">No name</span>}
                                    {isSelf && <span className="text-xs text-muted-foreground">(You)</span>}
                                  </div>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell className="text-muted-foreground text-sm">{member.user.email}</TableCell>
                            <TableCell>
                              <Badge variant={roleBadgeVariant(member.role)}>
                                {member.role.toUpperCase()}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {new Date(member.joined_at).toLocaleDateString()}
                            </TableCell>
                            <TableCell className="text-right">
                              {canManage && !isSelf && (member.role !== "owner" || user?.is_staff) && (
                                <div className="flex items-center justify-end gap-2">
                                  <DropdownMenu>
                                    <DropdownMenuTrigger 
                                      render={
                                        <Button 
                                          variant="outline" 
                                          size="sm" 
                                          className="h-8" 
                                          disabled={isChangingThisRole} 
                                        />
                                      }
                                    >
                                      {isChangingThisRole ? (
                                        <Loader2 className="h-4 w-4 animate-spin mr-1" />
                                      ) : null}
                                      Change Role <ChevronDown className="ml-2 h-4 w-4" />
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end">
                                      <DropdownMenuItem 
                                        onClick={() => handleChangeRole(member.id, "member")}
                                        disabled={member.role === "member"}
                                      >
                                        Member {member.role === "member" && <Check className="ml-auto h-4 w-4" />}
                                      </DropdownMenuItem>
                                      <DropdownMenuItem 
                                        onClick={() => handleChangeRole(member.id, "admin")}
                                        disabled={member.role === "admin"}
                                      >
                                        Admin {member.role === "admin" && <Check className="ml-auto h-4 w-4" />}
                                      </DropdownMenuItem>
                                      {(user?.is_staff || isOwner) && (
                                        <DropdownMenuItem 
                                          onClick={() => handleChangeRole(member.id, "owner")}
                                          disabled={member.role === "owner"}
                                        >
                                          Owner {member.role === "owner" && <Check className="ml-auto h-4 w-4" />}
                                        </DropdownMenuItem>
                                      )}
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                  <Button 
                                    variant="ghost" 
                                    size="sm" 
                                    className="text-destructive hover:text-destructive hover:bg-destructive/10 h-8"
                                    onClick={() => handleRemoveMember(member.id)}
                                    disabled={isRemovingThis}
                                  >
                                    {isRemovingThis ? <Loader2 className="h-4 w-4 animate-spin" /> : "Remove"}
                                  </Button>
                                </div>
                              )}
                              {isSelf && member.role !== "owner" && (
                                <Button 
                                  variant="ghost" 
                                  size="sm" 
                                  className="text-destructive hover:text-destructive hover:bg-destructive/10"
                                  onClick={() => handleRemoveMember(member.id)}
                                  disabled={isRemovingThis}
                                >
                                  {isRemovingThis ? <Loader2 className="h-4 w-4 animate-spin" /> : "Leave Team"}
                                </Button>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </div>
            )}

            {activeTab === "invitations" && canManage && (
              <TeamInvitationsTab teamId={activeTeam.id} />
            )}

            {activeTab === "settings" && canManage && (
              <TeamSettingsTab team={activeTeam} />
            )}

            {isInviteModalOpen && activeTeam && (
              <InviteMemberModal
                open={isInviteModalOpen}
                onOpenChange={(open: boolean) => setIsInviteModalOpen(open)}
                teamId={activeTeam.id}
                canInviteOwner={user?.is_staff || isOwner}
              />
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 rounded-xl border border-dashed text-muted-foreground text-sm">
            Select a team on the left to view its details.
          </div>
        )}
      </div>
    </div>
  );
}
