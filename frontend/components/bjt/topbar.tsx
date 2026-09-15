"use client";

import Link from "next/link";
import { 
  Menu, 
  Settings, 
  Users, 
  LogOut, 
  FolderGit2, 
  ListChecks, 
  Activity, 
  LineChart, 
  AlertTriangle, 
  BellRing, 
  BookOpen,
  ChevronRight,
  ShieldAlert
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Sidebar } from "./sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTeam } from "./team-provider";
import { logout } from "@/lib/api/auth";
import { useRouter, usePathname } from "next/navigation";
import { NotificationsPopover } from "./notifications/notifications-popover";
import { useAuth } from "@/hooks/use-auth";
import { UserAvatar } from "./user-avatar";
import { ProjectSelectFilter } from "./project-select-filter";

const pageMeta: Record<string, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
  "/projects": { label: "Projects", icon: FolderGit2 },
  "/jobs": { label: "Jobs", icon: ListChecks },
  "/executions": { label: "Executions", icon: Activity },
  "/analytics": { label: "Analytics", icon: LineChart },
  "/alerts": { label: "Alerts", icon: BellRing },
  "/incidents": { label: "Incidents", icon: AlertTriangle },
  "/runbooks": { label: "Runbooks", icon: BookOpen },
  "/team": { label: "Team", icon: Users },
  "/settings": { label: "Settings", icon: Settings },
  "/admin/channels": { label: "Notification Channels", icon: ShieldAlert },
  "/admin/policies": { label: "Notification Policies", icon: ShieldAlert },
};

export function Topbar() {
  const router = useRouter();
  const pathname = usePathname();
  const { activeTeam } = useTeam();
  const { user } = useAuth();

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // Ignore errors if already logged out
    } finally {
      router.push("/login");
    }
  };

  // Resolve current active page title and icon
  const currentRouteKey = Object.keys(pageMeta).find(
    (prefix) => pathname === prefix || pathname.startsWith(prefix + "/")
  );
  const currentRoute = currentRouteKey ? pageMeta[currentRouteKey] : null;
  const RouteIcon = currentRoute?.icon;

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border/60 bg-background/80 px-4 backdrop-blur-md lg:h-[60px] lg:px-6">
      {/* Mobile navigation toggle and brand */}
      <div className="flex items-center gap-2.5 md:hidden">
        <Sheet>
          <SheetTrigger render={<Button variant="ghost" size="icon" className="h-9 w-9 shrink-0" />}>
            <Menu className="h-5 w-5" />
            <span className="sr-only">Toggle navigation menu</span>
          </SheetTrigger>
          <SheetContent side="left" className="flex flex-col p-0 w-[280px]">
            <Sidebar />
          </SheetContent>
        </Sheet>

        <Link href="/" className="flex items-center gap-2">
          <img
            src="/bjt-logo-clean.png"
            alt="Background Job Tracker"
            className="h-6 w-auto object-contain"
          />
          <span className="font-semibold text-sm tracking-tight text-foreground truncate">
            Background Job Tracker
          </span>
        </Link>
      </div>
      {/* Desktop Brand Title & Context */}
      <div className="hidden md:flex items-center gap-2.5 text-sm">
        <Link 
          href="/" 
          className="text-base font-semibold tracking-tight text-foreground hover:opacity-90 transition-opacity"
        >
          Background Job Tracker
        </Link>
        {currentRoute && (
          <>
            <ChevronRight className="h-4 w-4 text-muted-foreground/60" />
            <div className="flex items-center gap-1.5 font-medium text-foreground bg-muted/60 px-2.5 py-1 rounded-md text-xs">
              {RouteIcon && <RouteIcon className="h-3.5 w-3.5 text-primary" />}
              <span>{currentRoute.label}</span>
            </div>
          </>
        )}
      </div>

      <div className="flex-1" />

      {/* Global Project Switcher */}
      <ProjectSelectFilter className="hidden sm:block w-44 lg:w-48" triggerClassName="h-8 bg-muted/40 border-border/60 hover:bg-muted text-xs font-medium" />

      {/* Notification Bell */}
      <NotificationsPopover />

      <div className="h-4 w-px bg-border/60 mx-0.5" />

      {/* User profile menu */}
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              className="rounded-full h-8 w-8 p-0 overflow-hidden ring-1 ring-border/60 hover:ring-primary/50 transition-all"
            />
          }
        >
          <UserAvatar user={user} size="sm" />
          <span className="sr-only">Toggle user menu</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuGroup>
            <DropdownMenuLabel className="flex flex-col gap-0.5 py-2">
              <span className="font-semibold text-sm leading-tight text-foreground">
                {user?.first_name ? `${user.first_name} ${user.last_name || ""}`.trim() : "My Account"}
              </span>
              {user?.email && (
                <span className="text-xs font-normal text-muted-foreground truncate">{user.email}</span>
              )}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push("/settings")} className="cursor-pointer">
              <Settings className="h-4 w-4 mr-2 text-muted-foreground" />
              <span>Settings</span>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push("/team")} className="cursor-pointer">
              <Users className="h-4 w-4 mr-2 text-muted-foreground" />
              <span>Team & Members</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive focus:text-destructive">
              <LogOut className="h-4 w-4 mr-2" />
              <span>Log out</span>
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
