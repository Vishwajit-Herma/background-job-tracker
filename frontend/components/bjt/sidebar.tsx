"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  FolderGit2, 
  Activity, 
  ListChecks, 
  LineChart,
  BellRing,
  AlertTriangle,
  Users,
  Settings,
  LogOut,
  Shield,
  MessageSquare,
  BookOpen
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useTeam } from "./team-provider";

const routes = [
  { href: "/projects", label: "Projects", icon: FolderGit2 },
  { href: "/jobs", label: "Jobs", icon: ListChecks },
  { href: "/executions", label: "Executions", icon: Activity },
  { href: "/analytics", label: "Analytics", icon: LineChart },
  { href: "/alerts", label: "Alerts", icon: BellRing },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle },
  { href: "/runbooks", label: "Runbooks", icon: BookOpen },
  { href: "/team", label: "Team", icon: Users },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const { logout, user } = useAuth();
  const { teams } = useTeam();

  const hasAdminAccess = user?.is_staff || teams.some(t => t.my_role === "admin" || t.my_role === "owner");

  const handleLogout = async () => {
    try {
      await logout();
    } catch (e) {
      // Ignore errors if already logged out
    } finally {
      router.push("/login");
    }
  };

  return (
    <div className={cn("flex h-full w-full flex-col border-r bg-muted/40", className)}>
      <div className="flex h-14 items-center border-b px-4 lg:h-[60px] lg:px-6">
        <Link href="/" className="flex items-center gap-2.5 font-semibold group">
          <img
            src="/bjt-logo-clean.png"
            alt="Background Job Tracker Logo"
            className="h-7 w-auto object-contain transition-transform group-hover:scale-105"
          />
          <span className="font-semibold text-sm tracking-tight text-foreground">
            Background Job Tracker
          </span>
        </Link>
      </div>
      <div className="flex-1 overflow-auto py-2">
        <nav className="grid items-start px-2 text-sm font-medium lg:px-4">
          {routes.map((route) => {
            const Icon = route.icon;
            const active = pathname.startsWith(route.href);
            return (
              <Link
                key={route.href}
                href={route.href}
                prefetch={false}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 transition-all hover:text-primary",
                  active ? "bg-muted text-primary" : "text-muted-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {route.label}
              </Link>
            );
          })}

          {hasAdminAccess && (
            <>
              <div className="mt-4 mb-2 px-4 text-xs font-semibold tracking-tight text-muted-foreground uppercase">
                Admin
              </div>
              <Link
                href="/admin/channels"
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 transition-all hover:text-primary",
                  pathname.startsWith("/admin/channels") ? "bg-muted text-primary" : "text-muted-foreground"
                )}
              >
                <MessageSquare className="h-4 w-4" />
                Notification Channels
              </Link>
              <Link
                href="/admin/policies"
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 transition-all hover:text-primary",
                  pathname.startsWith("/admin/policies") ? "bg-muted text-primary" : "text-muted-foreground"
                )}
              >
                <Shield className="h-4 w-4" />
                Notification Policies
              </Link>
            </>
          )}

          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-destructive hover:bg-destructive/10 mt-2"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </nav>
      </div>
    </div>
  );
}
