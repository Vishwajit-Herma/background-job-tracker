"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import Link from "next/link";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, Loader2, CheckCircle2 } from "lucide-react";

const resetPasswordSchema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

export default function ResetPasswordPage() {
  const params = useParams();
  const { resetPasswordConfirm } = useAuth();
  
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
  });

  const onSubmit = async (data: ResetPasswordFormValues) => {
    setGlobalError(null);
    setIsSubmitting(true);
    
    const uid = typeof params.uid === "string" ? params.uid : "";
    const token = typeof params.token === "string" ? params.token : "";

    try {
      await resetPasswordConfirm({
        uid,
        token,
        new_password1: data.password,
        new_password2: data.confirmPassword,
      });
      setSuccess(true);
    } catch (err: unknown) {
      const apiError = err as ApiError;
      if (apiError.status === 400 && apiError.errors) {
        Object.keys(apiError.errors).forEach((key) => {
          if (key === "non_field_errors" || key === "token" || key === "uid" || key === "detail") {
            setGlobalError((apiError.errors as any)[key].join(", "));
          } else {
            setError(key as keyof ResetPasswordFormValues, {
              type: "server",
              message: Array.isArray((apiError.errors as any)[key]) 
                ? (apiError.errors as any)[key].join(", ") 
                : String((apiError.errors as any)[key]),
            });
          }
        });
      } else {
        setGlobalError("Failed to reset password. The link may have expired.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="mx-auto flex w-full flex-col justify-center space-y-6 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12 text-green-500" />
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">Password Reset Successfully</h1>
          <p className="text-sm text-muted-foreground">
            Your password has been successfully reset. You can now log in with your new password.
          </p>
        </div>
        <Link href="/login" className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50">
          Go to Login
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full flex-col justify-center space-y-6">
      <div className="flex flex-col space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Reset your password</h1>
        <p className="text-sm text-muted-foreground">
          Enter your new password below.
        </p>
      </div>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="password">New Password</Label>
          <Input
            id="password"
            type="password"
            disabled={isSubmitting}
            {...register("password")}
          />
          {errors.password && (
            <p className="text-sm text-destructive">{errors.password.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirmPassword">Confirm New Password</Label>
          <Input
            id="confirmPassword"
            type="password"
            disabled={isSubmitting}
            {...register("confirmPassword")}
          />
          {errors.confirmPassword && (
            <p className="text-sm text-destructive">{errors.confirmPassword.message}</p>
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
          Reset Password
        </Button>
      </form>
    </div>
  );
}
