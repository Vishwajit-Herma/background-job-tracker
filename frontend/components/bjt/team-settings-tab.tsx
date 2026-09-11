"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Team, updateTeam, deleteTeam } from "@/lib/api/teams";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useRouter } from "next/navigation";
import { toastError, toastSuccess } from "@/lib/toast";
import { useTeam } from "./team-provider";

interface TeamSettingsTabProps {
  team: Team;
}

export function TeamSettingsTab({ team }: TeamSettingsTabProps) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { setActiveTeam } = useTeam();

  const [name, setName] = useState(team.name);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const handleUpdate = async () => {
    setIsUpdating(true);
    try {
      await updateTeam(team.id, { name });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      toastSuccess("Team updated successfully");
    } catch (e: any) {
      toastError("Failed to update team", e);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await deleteTeam(team.id);
      setActiveTeam(null);
      await queryClient.invalidateQueries({ queryKey: ["teams"] });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      toastSuccess("Team deleted successfully");
      setConfirmDeleteOpen(false);
      router.push("/team");
    } catch (e: any) {
      toastError("Failed to delete team. You must be the owner.", e);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Team Details</CardTitle>
          <CardDescription>Update your team's general settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2 max-w-md">
            <Label htmlFor="teamName">Team Name</Label>
            <Input 
              id="teamName" 
              value={name} 
              onChange={(e) => setName(e.target.value)} 
            />
          </div>
        </CardContent>
        <CardFooter>
          <Button onClick={handleUpdate} disabled={isUpdating || name === team.name}>
            {isUpdating ? "Saving..." : "Save Changes"}
          </Button>
        </CardFooter>
      </Card>

      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="text-destructive">Danger Zone</CardTitle>
          <CardDescription>Permanently delete this team and all its data.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="destructive" onClick={() => setConfirmDeleteOpen(true)}>
            Delete Team
          </Button>
        </CardContent>
      </Card>

      <Dialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Team</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete <span className="font-semibold text-foreground">{team.name}</span>? All
              associated projects, jobs, and executions will be permanently removed. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmDeleteOpen(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? "Deleting..." : "Confirm Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
