"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { inviteUser } from "@/lib/api/teams";
import { ApiError } from "@/lib/api/client";

const inviteSchema = z.object({
  email: z.string().email("Please enter a valid email"),
  role: z.enum(["owner", "admin", "member"]),
});

type InviteFormValues = z.infer<typeof inviteSchema>;

export function InviteMemberModal({
  teamId,
  open,
  onOpenChange,
  canInviteOwner = false,
}: {
  teamId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  canInviteOwner?: boolean;
}) {
  const queryClient = useQueryClient();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InviteFormValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { role: "member" },
  });

  const onSubmit = async (data: InviteFormValues) => {
    setErrorMsg(null);
    try {
      await inviteUser(teamId, data.email, data.role);
      queryClient.invalidateQueries({ queryKey: ["team-invitations", teamId] });
      reset();
      onOpenChange(false);
    } catch (e: any) {
      const err = e as ApiError;
      if (err.errors?.email) {
        setErrorMsg(Array.isArray(err.errors.email) ? err.errors.email[0] : String(err.errors.email));
      } else {
        setErrorMsg(err.message || "Failed to invite user");
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite Team Member</DialogTitle>
          <DialogDescription>
            Send an invitation to join your team.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              placeholder="user@example.com"
              {...register("email")}
            />
            {errors.email && (
              <p className="text-sm text-destructive">{errors.email.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="role">Role</Label>
            <select
              id="role"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              {...register("role")}
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
              {canInviteOwner && <option value="owner">Owner</option>}
            </select>
          </div>
          
          {errorMsg && (
            <div className="text-sm text-destructive font-medium">{errorMsg}</div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Sending..." : "Send Invite"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
