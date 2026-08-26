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

export function Topbar() {
  const router = useRouter();
  const { activeTeam } = useTeam();

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
        <DropdownMenuTrigger render={<Button variant="secondary" size="icon" className="rounded-full" />}>
          <UserCircle className="h-5 w-5" />
          <span className="sr-only">Toggle user menu</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            <DropdownMenuLabel>My Account</DropdownMenuLabel>
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
