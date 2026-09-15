"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import Link from "next/link";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { GoogleAuthButton } from "@/components/bjt/google-auth-button";

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const { login, isLoggingIn } = useAuth();
  const [errorMsg, setErrorMsg] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const error = params.get("error");
      if (error === "oauth_error") {
        return "Google sign-in was cancelled or encountered an authentication error.";
      }
      if (error === "oauth_unverified") {
        return "Cannot link account: The Google email is not verified by Google.";
      }
    }
    return null;
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormValues) => {
    setErrorMsg(null);
    try {
      await login(data);
    } catch (error) {
      const err = error as ApiError;
      setErrorMsg(err.message || "An unexpected error occurred. Please try again.");
    }
  };

  return (
    <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[350px]">
      <div className="flex flex-col space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
        <p className="text-sm text-muted-foreground">
          Enter your email and password to log in
        </p>
      </div>

      <div className="grid gap-4">
        <GoogleAuthButton label="Continue with Google" />

        <div className="relative my-1">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-background px-2 text-muted-foreground">Or continue with</span>
          </div>
        </div>

        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                placeholder="name@example.com"
                type="email"
                autoCapitalize="none"
                autoComplete="email"
                autoCorrect="off"
                disabled={isLoggingIn}
                {...register("email")}
              />
              {errors.email && (
                <p className="text-sm text-destructive">{errors.email.message}</p>
              )}
            </div>
            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <Link
                  href="/forgot-password"
                  className="text-sm font-medium text-muted-foreground hover:text-primary underline-offset-4 hover:underline"
                >
                  Forgot password?
                </Link>
              </div>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                disabled={isLoggingIn}
                {...register("password")}
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
            
            {errorMsg && (
              <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <p>{errorMsg}</p>
              </div>
            )}

            <Button disabled={isLoggingIn} type="submit" className="w-full">
              {isLoggingIn ? "Logging in..." : "Log in"}
            </Button>
          </div>
        </form>
      </div>

      <div className="text-center text-sm">
        Don&apos;t have an account?{" "}
        <Link href="/register" className="underline underline-offset-4 hover:text-primary">
          Sign up
        </Link>
      </div>
    </div>
  );
}
