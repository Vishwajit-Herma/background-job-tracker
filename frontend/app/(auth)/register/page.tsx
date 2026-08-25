"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import Link from "next/link";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, Loader2 } from "lucide-react";

const registerSchema = z
  .object({
    email: z.string().email("Invalid email address"),
    password1: z.string().min(8, "Password must be at least 8 characters"),
    password2: z.string(),
  })
  .refine((data) => data.password1 === data.password2, {
    message: "Passwords do not match",
    path: ["password2"],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const { register, isRegistering } = useAuth();
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const {
    register: formRegister,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormValues) => {
    setGlobalError(null);
    try {
      await register({
        email: data.email,
        password1: data.password1,
        password2: data.password2,
      });
      setSuccess(true);
    } catch (err: unknown) {
      const apiError = err as ApiError;
      if (apiError.status === 400 && apiError.errors) {
        // Map backend validation errors
        Object.keys(apiError.errors).forEach((key) => {
          if (key === "non_field_errors" || key === "detail") {
            setGlobalError((apiError.errors as any)[key].join(", "));
          } else {
            setError(key as keyof RegisterFormValues, {
              type: "server",
              message: Array.isArray((apiError.errors as any)[key]) 
                ? (apiError.errors as any)[key].join(", ") 
                : String((apiError.errors as any)[key]),
            });
          }
        });
      } else {
        setGlobalError("Registration failed. Please try again later.");
      }
    }
  };

  if (success) {
    return (
      <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[350px]">
        <div className="flex flex-col space-y-2 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">Check your email</h1>
          <p className="text-sm text-muted-foreground">
            We've sent a verification link to your email address. Please verify your account to continue.
          </p>
        </div>
        <Link href="/login" className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50">
          Go to Login
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[350px]">
      <div className="flex flex-col space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Create an account</h1>
        <p className="text-sm text-muted-foreground">
          Enter your email below to create your account
        </p>
      </div>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            placeholder="m@example.com"
            disabled={isRegistering}
            {...formRegister("email")}
          />
          {errors.email && (
            <p className="text-sm text-destructive">{errors.email.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="password1">Password</Label>
          <Input
            id="password1"
            type="password"
            disabled={isRegistering}
            {...formRegister("password1")}
          />
          {errors.password1 && (
            <p className="text-sm text-destructive">{errors.password1.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="password2">Confirm Password</Label>
          <Input
            id="password2"
            type="password"
            disabled={isRegistering}
            {...formRegister("password2")}
          />
          {errors.password2 && (
            <p className="text-sm text-destructive">{errors.password2.message}</p>
          )}
        </div>

        {globalError && (
          <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
            <AlertCircle className="h-4 w-4" />
            <p>{globalError}</p>
          </div>
        )}

        <Button type="submit" className="w-full" disabled={isRegistering}>
          {isRegistering && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Register
        </Button>
      </form>

      <div className="text-center text-sm">
        Already have an account?{" "}
        <Link href="/login" className="underline underline-offset-4 hover:text-primary">
          Log in
        </Link>
      </div>
    </div>
  );
}
