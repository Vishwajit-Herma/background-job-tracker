"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  LayoutDashboard, 
  FolderGit2, 
  Activity, 
  ListChecks, 
  LineChart,
  BellRing,
  AlertTriangle,
  Users,
  Settings,
  Key,
  LogOut
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";

const routes = [
  { href: "/projects", label: "Projects", icon: FolderGit2 },
  { href: "/jobs", label: "Jobs", icon: ListChecks },
  { href: "/executions", label: "Executions", icon: Activity },
  { href: "/analytics", label: "Analytics", icon: LineChart },
  { href: "/alerts", label: "Alerts", icon: BellRing },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle },
  { href: "/team", label: "Team", icon: Users },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();

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
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <LayoutDashboard className="h-6 w-6" />
          <span className="">BJT</span>
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
