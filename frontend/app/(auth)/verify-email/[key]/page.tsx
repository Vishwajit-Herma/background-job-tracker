"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";
import Link from "next/link";
import { apiClient } from "@/lib/api/client";

export default function VerifyEmailPage() {
  const params = useParams();
  const router = useRouter();
  const { verifyEmail } = useAuth();
  
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [email, setEmail] = useState("");
  const [resendStatus, setResendStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const hasVerified = useRef(false);

  useEffect(() => {
    const key = params.key;
    if (typeof key !== "string") {
      setStatus("error");
      return;
    }

    if (hasVerified.current) return;
    hasVerified.current = true;

    verifyEmail(key)
      .then(() => {
        setStatus("success");
      })
      .catch(() => {
        setStatus("error");
      });
  }, [params.key, verifyEmail]);

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
    <div className="flex min-h-screen items-center justify-center px-4 bg-background">
      <div className="flex w-full max-w-[400px] flex-col items-center justify-center space-y-6 text-center">
        {status === "loading" && (
          <>
            <Loader2 className="h-12 w-12 animate-spin text-primary" />
            <h1 className="text-2xl font-semibold tracking-tight">Verifying your email...</h1>
            <p className="text-sm text-muted-foreground">
              Please wait while we confirm your email address.
            </p>
          </>
        )}

        {status === "success" && (
          <>
            <CheckCircle2 className="h-12 w-12 text-green-500" />
            <h1 className="text-2xl font-semibold tracking-tight">Email Verified!</h1>
            <p className="text-sm text-muted-foreground">
              Your email address has been successfully verified. You can now log in to your account.
            </p>
            <Link href="/login" className="mt-4 inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 w-full">
              Go to Login
            </Link>
          </>
        )}

        {status === "error" && (
          <>
            <XCircle className="h-12 w-12 text-destructive" />
            <h1 className="text-2xl font-semibold tracking-tight">Link Expired or Invalid</h1>
            <p className="text-sm text-muted-foreground">
              This verification link is invalid, has expired, or your email is already verified.
            </p>

            <form onSubmit={handleResend} className="flex w-full flex-col space-y-3 mt-4">
              <input
                type="email"
                placeholder="Enter your email"
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
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

            <Link href="/login" className="mt-4 inline-flex h-9 items-center justify-center w-full rounded-md border border-input bg-transparent px-4 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50">
              Back to Login
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
