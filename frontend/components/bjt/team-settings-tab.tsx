"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Team, updateTeam, deleteTeam } from "@/lib/api/teams";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { useRouter } from "next/navigation";

export function TeamSettingsTab({ team }: { team: Team }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  
  const [name, setName] = useState(team.name);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleUpdate = async () => {
    setIsUpdating(true);
    try {
      await updateTeam(team.id, { name });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      alert("Team updated successfully");
    } catch (e) {
      alert("Failed to update team");
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this team? This action cannot be undone.")) return;
    
    setIsDeleting(true);
    try {
      await deleteTeam(team.id);
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      router.push("/");
    } catch (e) {
      alert("Failed to delete team. You must be the owner.");
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
          <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
            {isDeleting ? "Deleting..." : "Delete Team"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
