"use client";

import { Bell, Menu, UserCircle, Users } from "lucide-react";
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

export function Topbar() {
  const router = useRouter();
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

  return (
    <header className="flex h-14 items-center gap-4 border-b bg-muted/40 px-4 lg:h-[60px] lg:px-6">
      {/* Mobile nav toggle */}
      <Sheet>
        <SheetTrigger render={<Button variant="outline" size="icon" className="shrink-0 md:hidden" />}>
          <Menu className="h-5 w-5" />
          <span className="sr-only">Toggle navigation menu</span>
        </SheetTrigger>
        <SheetContent side="left" className="flex flex-col p-0">
          <Sidebar />
        </SheetContent>
      </Sheet>

      <div className="flex-1" />

      {/* Notification bell */}
      <NotificationsPopover />

      {/* User menu */}
      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button variant="ghost" size="icon" className="rounded-full h-8 w-8 p-0 overflow-hidden ring-1 ring-border/60 hover:ring-primary/50" />}
        >
          <UserAvatar user={user} size="sm" />
          <span className="sr-only">Toggle user menu</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            <DropdownMenuLabel className="flex flex-col">
              <span>{user?.first_name ? `${user.first_name} ${user.last_name || ""}`.trim() : "My Account"}</span>
              {user?.email && <span className="text-xs font-normal text-muted-foreground">{user.email}</span>}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push("/settings")}>Settings</DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push("/team")}>Team</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>Logout</DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
