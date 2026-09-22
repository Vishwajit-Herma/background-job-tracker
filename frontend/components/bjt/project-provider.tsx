"use client";

import React, { createContext, useContext, useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getProjects, Project } from "@/lib/api/projects";
import { useTeam } from "./team-provider";

interface ProjectContextType {
  selectedProjectId: number | "all";
  setSelectedProjectId: (id: number | "all") => void;
  selectedProject: Project | null;
  projects: Project[];
  isLoading: boolean;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

const STORAGE_KEY = "bjt_selected_project_id";

function UrlProjectSyncer({
  selectedProjectId,
  setSelectedProjectId,
}: {
  selectedProjectId: number | "all";
  setSelectedProjectId: (id: number | "all") => void;
}) {
  const searchParams = useSearchParams();
  const projectParam = searchParams.get("project");

  useEffect(() => {
    if (!projectParam) return;
    if (projectParam === "all") {
      if (selectedProjectId !== "all") {
        setSelectedProjectId("all");
      }
    } else {
      const parsed = parseInt(projectParam, 10);
      if (!isNaN(parsed) && parsed !== selectedProjectId) {
        setSelectedProjectId(parsed);
      }
    }
  }, [projectParam, selectedProjectId, setSelectedProjectId]);

  return null;
}

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const { activeTeam } = useTeam();
  const [selectedProjectId, setSelectedProjectIdState] = useState<number | "all">("all");

  // Fetch projects belonging to active team
  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ["projects", activeTeam?.id],
    queryFn: () => getProjects(),
    enabled: !!activeTeam,
  });

  // Restore saved selection on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        if (saved === "all") {
          setSelectedProjectIdState("all");
        } else {
          const parsed = parseInt(saved, 10);
          if (!isNaN(parsed)) {
            setSelectedProjectIdState(parsed);
          }
        }
      }
    } catch {
      // Ignore localStorage errors
    }
  }, []);

  // Sync state and persist to localStorage
  const setSelectedProjectId = (id: number | "all") => {
    setSelectedProjectIdState(id);
    try {
      localStorage.setItem(STORAGE_KEY, id.toString());
    } catch {
      // Ignore localStorage errors
    }
  };

  // Validate that selectedProjectId is valid for current team's projects
  useEffect(() => {
    if (selectedProjectId !== "all" && projects.length > 0) {
      const exists = projects.some((p) => p.id === selectedProjectId);
      if (!exists) {
        setSelectedProjectIdState("all");
        localStorage.setItem(STORAGE_KEY, "all");
      }
    }
  }, [projects, selectedProjectId]);

  const selectedProject =
    selectedProjectId !== "all" ? projects.find((p) => p.id === selectedProjectId) || null : null;

  return (
    <ProjectContext.Provider
      value={{
        selectedProjectId,
        setSelectedProjectId,
        selectedProject,
        projects,
        isLoading,
      }}
    >
      <Suspense fallback={null}>
        <UrlProjectSyncer
          selectedProjectId={selectedProjectId}
          setSelectedProjectId={setSelectedProjectId}
        />
      </Suspense>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return context;
}
