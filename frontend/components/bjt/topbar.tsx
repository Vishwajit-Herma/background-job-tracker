"use client";

import { useState } from "react";
import { Bell, Menu, UserCircle, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Sidebar } from "./sidebar";
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuLabel, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger,
  DropdownMenuGroup
} from "@/components/ui/dropdown-menu";
import { useTeam } from "./team-provider";
import { Check } from "lucide-react";
import { logout } from "@/lib/api/auth";
import { useRouter } from "next/navigation";
import { CreateTeamModal } from "./create-team-modal";

export function Topbar() {
  const router = useRouter();
  const { teams, activeTeam, setActiveTeam } = useTeam();
  const [isCreateTeamOpen, setIsCreateTeamOpen] = useState(false);

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
    <>
      <header className="flex h-14 items-center gap-4 border-b bg-muted/40 px-4 lg:h-[60px] lg:px-6">
        <Sheet>
          <SheetTrigger render={<Button variant="outline" size="icon" className="shrink-0 md:hidden" />}>
            <Menu className="h-5 w-5" />
            <span className="sr-only">Toggle navigation menu</span>
          </SheetTrigger>
          <SheetContent side="left" className="flex flex-col p-0">
            <Sidebar />
          </SheetContent>
        </Sheet>
        
        <div className="w-full flex-1 flex items-center">
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="outline" className="w-[200px] justify-between" />}>
              {activeTeam ? activeTeam.name : "Select Team"}
              <Check className="ml-2 h-4 w-4 opacity-0" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-[200px]">
              <DropdownMenuGroup>
                <DropdownMenuLabel>Teams</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {teams.map((team) => (
                  <DropdownMenuItem 
                    key={team.id} 
                    onClick={() => setActiveTeam(team)}
                    className="justify-between"
                  >
                    {team.name}
                    {activeTeam?.id === team.id && <Check className="h-4 w-4" />}
                  </DropdownMenuItem>
                ))}
                {teams.length === 0 && (
                  <DropdownMenuItem disabled>No teams available</DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => setIsCreateTeamOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Create Team
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <Button variant="outline" size="icon" className="ml-auto h-8 w-8 relative">
          <Bell className="h-4 w-4" />
          <span className="sr-only">Toggle notifications</span>
          <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-destructive"></span>
        </Button>

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

      <CreateTeamModal 
        open={isCreateTeamOpen} 
        onOpenChange={setIsCreateTeamOpen} 
      />
    </>
  );
}
