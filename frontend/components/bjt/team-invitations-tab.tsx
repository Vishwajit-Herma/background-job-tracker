"use client";

import { useQuery } from "@tanstack/react-query";
import { getInvitations } from "@/lib/api/teams";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export function TeamInvitationsTab({ teamId }: { teamId: number }) {
  const { data: invitations = [], isLoading } = useQuery({
    queryKey: ["team-invitations", teamId],
    queryFn: () => getInvitations(teamId),
  });

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Email</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Sent At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invitations.length === 0 && !isLoading ? (
            <TableRow>
              <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                No pending invitations.
              </TableCell>
            </TableRow>
          ) : (
            invitations.map((invite) => (
              <TableRow key={invite.id}>
                <TableCell className="font-medium">{invite.email}</TableCell>
                <TableCell>
                  <Badge variant="outline">{invite.role.toUpperCase()}</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{invite.status}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {new Date(invite.created_at).toLocaleDateString()}
                </TableCell>
              </TableRow>
            ))
          )}
          
          {isLoading && (
            <TableRow>
              <TableCell colSpan={4} className="h-24 text-center">
                Loading invitations...
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
