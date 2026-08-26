import { useQuery } from "@tanstack/react-query";
import { getProjects, Project } from "@/lib/api/projects";
import { getTeams, Team } from "@/lib/api/teams";
import { getJobs, Job } from "@/lib/api/jobs";
import { getAlertRules, AlertRule } from "@/lib/api/alerts";

// Cache for 5 minutes to prevent redundant API calls across navigations
const STALE_TIME = 5 * 60 * 1000;

export function useWorkspace() {
  const {
    data: teams = [],
    isLoading: isLoadingTeams,
    isError: isErrorTeams,
  } = useQuery<Team[]>({
    queryKey: ["teams"],
    queryFn: getTeams,
    staleTime: STALE_TIME,
  });

  const {
    data: projects = [],
    isLoading: isLoadingProjects,
    isError: isErrorProjects,
  } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: () => getProjects(),
    staleTime: STALE_TIME,
  });

  const {
    data: jobs = [],
    isLoading: isLoadingJobs,
    isError: isErrorJobs,
  } = useQuery<Job[]>({
    queryKey: ["jobs"],
    queryFn: () => getJobs(),
    staleTime: STALE_TIME,
  });

  const {
    data: alertRules = [],
    isLoading: isLoadingAlerts,
    isError: isErrorAlerts,
  } = useQuery<AlertRule[]>({
    queryKey: ["alert-rules"],
    queryFn: () => getAlertRules(),
    staleTime: STALE_TIME,
  });

  // Derived state maps for quick lookup
  const teamMap = new Map(teams.map((t) => [t.id, t]));
  const projectMap = new Map(projects.map((p) => [p.id, p]));
  const jobMap = new Map(jobs.map((j) => [j.id, j]));
  const alertRuleMap = new Map(alertRules.map((r) => [r.id, r]));

  // RBAC Helpers
  const canManageTeam = (teamId: number) => {
    const team = teamMap.get(teamId);
    if (!team) return false;
    return team.my_role === "admin" || team.my_role === "owner";
  };

  const canManageProject = (projectId: number) => {
    const project = projectMap.get(projectId);
    if (!project) return false;
    return canManageTeam(project.team);
  };

  return {
    teams,
    projects,
    jobs,
    alertRules,
    teamMap,
    projectMap,
    jobMap,
    alertRuleMap,
    canManageTeam,
    canManageProject,
    isLoading: isLoadingTeams || isLoadingProjects || isLoadingJobs || isLoadingAlerts,
    isError: isErrorTeams || isErrorProjects || isErrorJobs || isErrorAlerts,
  };
}
