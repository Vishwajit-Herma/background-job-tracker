"use client";

import { createContext, useContext, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTeams, Team } from "@/lib/api/teams";
import { useAuth } from "@/hooks/use-auth";
import { useRouter, usePathname } from "next/navigation";

const ACTIVE_TEAM_KEY = "bjt_active_team_id";

interface TeamContextType {
  teams: Team[];
  activeTeam: Team | null;
  setActiveTeam: (team: Team | null) => void;
  isLoading: boolean;
}

const TeamContext = createContext<TeamContextType | undefined>(undefined);

export function TeamProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  
  const { data: teams = [], isLoading } = useQuery({
    queryKey: ["teams"],
    queryFn: () => getTeams(),
    enabled: !!user,
  });

  const [activeTeamId, setActiveTeamId] = useState<number | null>(() => {
    if (typeof window === "undefined") return null;
    const stored = localStorage.getItem(ACTIVE_TEAM_KEY);
    return stored ? parseInt(stored, 10) : null;
  });

  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Onboarding redirect removed. Users can now use the dashboard without a team.
  }, [isLoading, user, teams.length, pathname, router]);

  // Resolve active team: prefer stored ID, fallback to first team
  const resolvedActiveTeam =
    (activeTeamId ? (teams as Team[]).find((t: Team) => t.id === activeTeamId) : null) ||
    ((teams as Team[]).length > 0 ? (teams as Team[])[0] : null);

  const setActiveTeam = (team: Team | null) => {
    setActiveTeamId(team?.id ?? null);
    if (team) {
      localStorage.setItem(ACTIVE_TEAM_KEY, String(team.id));
    } else {
      localStorage.removeItem(ACTIVE_TEAM_KEY);
    }
  };

  return (
    <TeamContext.Provider value={{ teams, activeTeam: resolvedActiveTeam, setActiveTeam, isLoading }}>
      {children}
    </TeamContext.Provider>
  );
}

export function useTeam() {
  const context = useContext(TeamContext);
  if (context === undefined) {
    throw new Error("useTeam must be used within a TeamProvider");
  }
  return context;
}
