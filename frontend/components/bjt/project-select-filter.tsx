"use client";

import { useProject } from "./project-provider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { FolderGit2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProjectSelectFilterProps {
  className?: string;
  triggerClassName?: string;
}

export function ProjectSelectFilter({ className = "w-full sm:w-48", triggerClassName = "h-9" }: ProjectSelectFilterProps) {
  const { selectedProjectId, setSelectedProjectId, projects, isLoading } = useProject();

  const handleValueChange = (val: string) => {
    if (val === "all") {
      setSelectedProjectId("all");
    } else {
      const num = parseInt(val, 10);
      if (!isNaN(num)) {
        setSelectedProjectId(num);
      }
    }
  };

  const selectedProject = selectedProjectId !== "all" ? projects.find((p) => p.id === selectedProjectId) : null;

  return (
    <div className={className}>
      <Select
        value={selectedProjectId.toString()}
        onValueChange={handleValueChange}
        disabled={isLoading}
      >
        <SelectTrigger className={triggerClassName}>
          <div className="flex items-center gap-2 truncate">
            <FolderGit2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            {selectedProjectId === "all" ? (
              <span className="truncate font-medium">All Projects</span>
            ) : selectedProject ? (
              <div className="flex items-center gap-1.5 truncate">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full shrink-0",
                    selectedProject.status === "active" ? "bg-emerald-500" : "bg-muted-foreground/40"
                  )}
                  title={selectedProject.status === "active" ? "Active" : "Inactive"}
                />
                <span className="truncate">{selectedProject.name}</span>
              </div>
            ) : (
              <span>Project #{selectedProjectId}</span>
            )}
          </div>
        </SelectTrigger>
        <SelectContent align="start" className="w-[200px]">
          <SelectItem value="all">
            <div className="flex items-center gap-2 font-medium">
              <FolderGit2 className="h-3.5 w-3.5 text-muted-foreground" />
              <span>All Projects</span>
            </div>
          </SelectItem>
          {projects.map((project) => {
            const isActive = project.status === "active";
            return (
              <SelectItem key={project.id} value={project.id.toString()}>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full shrink-0",
                      isActive ? "bg-emerald-500" : "bg-muted-foreground/40"
                    )}
                  />
                  <span className="truncate">{project.name}</span>
                  {!isActive && (
                    <span className="text-[10px] text-muted-foreground ml-auto font-mono">
                      (inactive)
                    </span>
                  )}
                </div>
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
    </div>
  );
}
