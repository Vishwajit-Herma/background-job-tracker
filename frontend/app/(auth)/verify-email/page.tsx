"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Mail, Loader2 } from "lucide-react";
import Link from "next/link";
import { apiClient } from "@/lib/api/client";

export default function VerifyEmailPromptPage() {
  const [email, setEmail] = useState("");
  const [resendStatus, setResendStatus] = useState<"idle" | "loading" | "success" | "error">("idle");

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    setResendStatus("loading");
    try {
      await apiClient.post("/auth/registration/resend-email/", { email });
      setResendStatus("success");
    } catch (err) {
      setResendStatus("error");
    }
  };

  return (
    <div className="mx-auto flex w-full flex-col items-center justify-center space-y-6 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Mail className="h-6 w-6" />
      </div>

      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Verify Your Email</h1>
        <p className="text-sm text-muted-foreground">
          Please check your inbox and click the verification link we sent to complete your registration.
        </p>
      </div>

      <div className="w-full space-y-4 pt-2">
        <p className="text-xs text-muted-foreground">
          Didn't receive an email or link expired? Enter your email to resend:
        </p>

        <form onSubmit={handleResend} className="flex w-full flex-col space-y-3">
          <input
            type="email"
            placeholder="Enter your email"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Button type="submit" disabled={resendStatus === "loading" || !email} className="w-full">
            {resendStatus === "loading" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Resend Verification Link
          </Button>
        </form>

        {resendStatus === "success" && (
          <p className="text-sm text-green-600 font-medium bg-green-500/10 p-2 rounded w-full">
            Verification email sent! Check your inbox.
          </p>
        )}
        {resendStatus === "error" && (
          <p className="text-sm text-destructive font-medium bg-destructive/10 p-2 rounded w-full">
            Failed to send email. Please check the address and try again.
          </p>
        )}
      </div>

      <Link
        href="/login"
        className="inline-flex h-9 items-center justify-center w-full rounded-md border border-input bg-transparent px-4 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
      >
        Back to Login
      </Link>
    </div>
  );
}
