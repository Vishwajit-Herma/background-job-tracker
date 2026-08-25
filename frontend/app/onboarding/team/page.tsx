"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { createTeam } from "@/lib/api/teams";
import { ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AlertCircle, Loader2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

const teamSchema = z.object({
  name: z.string().min(3, "Team name must be at least 3 characters"),
  description: z.string().optional(),
});

type TeamFormValues = z.infer<typeof teamSchema>;

export default function OnboardingTeamPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<TeamFormValues>({
    resolver: zodResolver(teamSchema),
  });

  const onSubmit = async (data: TeamFormValues) => {
    setGlobalError(null);
    setIsSubmitting(true);
    try {
      await createTeam(data);
      // Invalidate teams query to trigger a refetch everywhere
      await queryClient.invalidateQueries({ queryKey: ["teams"] });
      // Redirect to dashboard
      router.push("/projects");
    } catch (err: unknown) {
      const apiError = err as ApiError;
      if (apiError.status === 400 && apiError.errors) {
        Object.keys(apiError.errors).forEach((key) => {
          if (key === "non_field_errors" || key === "detail") {
            setGlobalError((apiError.errors as any)[key].join(", "));
          } else {
            setError(key as keyof TeamFormValues, {
              type: "server",
              message: Array.isArray((apiError.errors as any)[key]) 
                ? (apiError.errors as any)[key].join(", ") 
                : String((apiError.errors as any)[key]),
            });
          }
        });
      } else {
        setGlobalError("Failed to create team. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex w-full max-w-[400px] flex-col justify-center space-y-6">
      <div className="flex flex-col space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Create your first team</h1>
        <p className="text-sm text-muted-foreground">
          A team represents your organization or workspace.
        </p>
      </div>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name">Team Name</Label>
          <Input
            id="name"
            placeholder="Acme Corp"
            disabled={isSubmitting}
            {...register("name")}
          />
          {errors.name && (
            <p className="text-sm text-destructive">{errors.name.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="description">Description (Optional)</Label>
          <Textarea
            id="description"
            placeholder="What is this team for?"
            disabled={isSubmitting}
            {...register("description")}
          />
          {errors.description && (
            <p className="text-sm text-destructive">{errors.description.message}</p>
          )}
        </div>

        {globalError && (
          <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
            <AlertCircle className="h-4 w-4" />
            <p>{globalError}</p>
          </div>
        )}

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Create Team & Continue
        </Button>
      </form>
    </div>
  );
}
