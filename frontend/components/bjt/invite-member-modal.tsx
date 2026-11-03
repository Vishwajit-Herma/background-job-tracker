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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<InviteFormValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { role: "member" },
  });

  const selectedRole = watch("role") ?? "member";

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
            <Select
              value={selectedRole}
              onValueChange={(val) => {
                if (val) setValue("role", val as "owner" | "admin" | "member", { shouldValidate: true });
              }}
            >
              <SelectTrigger id="role" className="w-full">
                <SelectValue placeholder="Select role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="member">Member</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
                {canInviteOwner && <SelectItem value="owner">Owner</SelectItem>}
              </SelectContent>
            </Select>
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
