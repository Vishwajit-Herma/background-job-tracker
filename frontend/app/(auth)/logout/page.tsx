"use client";

import { useEffect } from "react";
import { useAuth } from "@/hooks/use-auth";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

export default function LogoutPage() {
  const { logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Automatically trigger logout on mount and redirect
    logout()
      .catch(() => {
        // Ignore errors (e.g. if already logged out)
      })
      .finally(() => {
        router.push("/login");
      });
  }, [logout, router]);

  return (
    <div className="flex h-screen w-full items-center justify-center">
      <div className="flex flex-col items-center space-y-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Logging you out...</p>
      </div>
    </div>
  );
}
