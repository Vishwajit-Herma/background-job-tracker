"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useWorkspace } from "@/hooks/use-workspace";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, ListChecks, CheckCircle2, XCircle, Activity, Briefcase, Plus, MoreHorizontal, Pencil, Trash2, ToggleLeft, ToggleRight, Search, HelpCircle, ShieldCheck } from "lucide-react";
import { ExecutionsSheet } from "@/components/bjt/jobs/executions-sheet";
import { JobFormModal, ConfirmDeleteJobModal } from "@/components/bjt/jobs/job-modals";
import { useAuth } from "@/hooks/use-auth";
import { updateJob, getJobsPaginated } from "@/lib/api/jobs";
import { getProjectReliability, ReliabilityState } from "@/lib/api/reliability";
import { ReliabilityBadge } from "@/components/bjt/reliability/reliability-badge";
import { useDebounce } from "@/hooks/use-debounce";
import { PaginationControls } from "@/components/bjt/pagination";
import { useProject } from "@/components/bjt/project-provider";
import { ProjectSelectFilter } from "@/components/bjt/project-select-filter";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function JobsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const isGlobalStaff = user?.is_staff ?? false;
  const { selectedProjectId } = useProject();

  const [selectedJob, setSelectedJob] = useState<{ id: number; name: string } | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editJob, setEditJob] = useState<any | null>(null);
  const [deleteJob, setDeleteJob] = useState<any | null>(null);
  const [toggling, setToggling] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const [statusFilter, setStatusFilter] = useState("all");

  const reliabilityParam = searchParams?.get("reliability") || "all";
  const [reliabilityFilter, setReliabilityFilter] = useState(reliabilityParam);

  const { projects, jobs, teamMap, projectMap, isLoading: isLoadingWorkspace, isError: isWorkspaceError } = useWorkspace();
  const targetJobId = searchParams?.get("job_id");

  // Synchronize reliability filter with URL search params
  const handleReliabilityFilterChange = (val: string) => {
    setReliabilityFilter(val);
    const params = new URLSearchParams(searchParams?.toString() || "");
    if (val === "all") {
      params.delete("reliability");
    } else {
      params.set("reliability", val);
    }
    router.replace(`/jobs?${params.toString()}`);
  };

  // Fetch jobs with server-side pagination for the table
  const debouncedSearch = useDebounce(search, 500);

  const { data: paginatedJobs, isLoading: isLoadingJobs, isError: isJobsError, refetch } = useQuery({
    queryKey: ["jobs-paginated", page, debouncedSearch, ordering, statusFilter, selectedProjectId],
    queryFn: () => getJobsPaginated({ 
      page, 
      search: debouncedSearch, 
      ordering, 
      status: statusFilter !== "all" ? statusFilter : undefined,
      project: selectedProjectId !== "all" ? selectedProjectId : undefined,
    }),
  });

  // Query project reliability maps for all active projects
  const { data: projectReliabilityMap = {} } = useQuery({
    queryKey: ["project-reliability-map", projects.map(p => p.id)],
    queryFn: async () => {
      const map: Record<number, ReliabilityState> = {};
      const results = await Promise.all(
        projects.map(p => getProjectReliability(p.id).catch(() => null))
      );
      results.forEach(res => {
        if (res && res.jobs) {
          res.jobs.forEach(j => {
            map[j.job_id] = j.current_state;
          });
        }
      });
      return map;
    },
    enabled: projects.length > 0,
  });

  const pagedJobs = paginatedJobs?.data || [];
  const totalPages = paginatedJobs?.totalPages || 1;

  // Filter jobs by reliability state if filtered
  const displayedJobs = pagedJobs.filter(job => {
    if (reliabilityFilter === "all") return true;
    const state = projectReliabilityMap[job.id] || "HEALTHY";
    return state === reliabilityFilter;
  });

  // Reset to first page if current page becomes out of range
  useEffect(() => {
    if (!isLoadingJobs && pagedJobs.length === 0 && page > 1) {
      setPage(1);
    }
  }, [pagedJobs.length, isLoadingJobs, page]);

  const isLoading = isLoadingWorkspace || isLoadingJobs;
  const isError = isWorkspaceError || isJobsError;

  useEffect(() => {
    if (targetJobId && jobs.length > 0 && !selectedJob) {
      const j = jobs.find(j => j.id === Number(targetJobId));
      if (j) setSelectedJob({ id: j.id, name: j.name });
    }
  }, [targetJobId, jobs]);

  // Find which projects the user can manage (to pass to Create Job modal)
  const manageableProjects = projects.filter(p => {
    if (isGlobalStaff) return true;
    const t = teamMap.get(p.team);
    return t && (t.my_role === "admin" || t.my_role === "owner");
  });

  const queryClient = useQueryClient();
  const handleRefetch = () => {
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
    queryClient.invalidateQueries({ queryKey: ["jobs-paginated"] });
    queryClient.invalidateQueries({ queryKey: ["project-reliability-map"] });
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Jobs</h2>
          <p className="text-muted-foreground mt-1">
            All background jobs monitored across your projects.
          </p>
        </div>
        {manageableProjects.length > 0 && (
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> Create Job
          </Button>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-3 items-center justify-between bg-card p-3 rounded-md border">
        <div className="relative w-full lg:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search jobs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="flex flex-wrap w-full lg:w-auto gap-3">
          {/* Project Filter */}
          <ProjectSelectFilter className="w-full sm:w-44" />
          {/* Reliability Filter */}
          <div className="w-full sm:w-40">
            <Select value={reliabilityFilter} onValueChange={(val) => { if (val) handleReliabilityFilterChange(val); }}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Reliability">
                  {reliabilityFilter === "all" && "All Reliability"}
                  {reliabilityFilter === "HEALTHY" && "Healthy"}
                  {reliabilityFilter === "ANOMALOUS" && "Anomalous"}
                  {reliabilityFilter === "MISSED" && "Missed"}
                  {reliabilityFilter === "STALLED" && "Stalled"}
                  {reliabilityFilter === "OVERDUE" && "Overdue"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Reliability</SelectItem>
                <SelectItem value="HEALTHY">Healthy</SelectItem>
                <SelectItem value="ANOMALOUS">Anomalous</SelectItem>
                <SelectItem value="MISSED">Missed</SelectItem>
                <SelectItem value="STALLED">Stalled</SelectItem>
                <SelectItem value="OVERDUE">Overdue</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Status Filter */}
          <div className="w-full sm:w-36">
            <Select value={statusFilter} onValueChange={(val) => { if (val) setStatusFilter(val); }}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Status">
                  {statusFilter === "all" && "All Statuses"}
                  {statusFilter === "active" && "Active"}
                  {statusFilter === "inactive" && "Inactive"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Ordering Filter */}
          <div className="w-full sm:w-44">
            <Select value={ordering} onValueChange={(val) => { if (val) setOrdering(val); }}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Sort by">
                  {ordering === "-created_at" && "Newest First"}
                  {ordering === "created_at" && "Oldest First"}
                  {ordering === "name" && "Name (A-Z)"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="-created_at">Newest First</SelectItem>
                <SelectItem value="created_at">Oldest First</SelectItem>
                <SelectItem value="name">Name (A-Z)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground py-4">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Loading jobs...</span>
        </div>
      ) : isError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-destructive">
          Failed to load jobs. <button onClick={() => handleRefetch()} className="underline font-medium">Retry</button>
        </div>
      ) : displayedJobs.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 rounded-xl border border-dashed text-muted-foreground text-sm">
          <ListChecks className="h-10 w-10 mb-4 opacity-20" />
          <p>No jobs match the current filters.</p>
          <p className="text-xs mt-1">Jobs will appear here once your SDK starts reporting telemetry.</p>
        </div>
      ) : (
        <div className="rounded-md border bg-card overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Project</TableHead>
                <TableHead>Job Name</TableHead>
                <TableHead>Task Identifier</TableHead>
                <TableHead title="Schedule & runtime behavior adherence (Healthy, Missed, Stalled, Overdue).">Reliability <HelpCircle className="inline-block h-3 w-3 opacity-50 cursor-help mb-0.5" /></TableHead>
                <TableHead title="Real-time operational status (driven by active incidents).">Health <HelpCircle className="inline-block h-3 w-3 opacity-50 cursor-help mb-0.5" /></TableHead>
                <TableHead>Executions</TableHead>
                <TableHead>Success Rate</TableHead>
                <TableHead>Verification</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {displayedJobs.map((job) => {
                const project = projectMap.get(job.project as number);
                const t = project ? teamMap.get(project.team) : null;
                const canManage = isGlobalStaff || (t && (t.my_role === "admin" || t.my_role === "owner"));
                const reliabilityState = projectReliabilityMap[job.id] || "HEALTHY";

                return (
                  <TableRow key={job.id} className={job.status === "inactive" ? "opacity-60" : ""}>
                    <TableCell className="py-3">
                      <div className="flex items-center gap-1.5 font-medium text-sm">
                        <Briefcase className="h-3.5 w-3.5 text-muted-foreground" />
                        {project?.name || `Project #${job.project}`}
                      </div>
                    </TableCell>

                    <TableCell className="py-3 font-medium">
                      <Link
                        href={`/jobs/${job.id}`}
                        className="hover:underline text-foreground font-semibold hover:text-primary transition-colors"
                      >
                        {job.name}
                      </Link>
                      {job.description && (
                        <p className="text-xs text-muted-foreground truncate max-w-[250px] mt-0.5 font-normal">
                          {job.description}
                        </p>
                      )}
                    </TableCell>

                    <TableCell className="py-3">
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono break-all max-w-[250px] inline-block truncate" title={job.task_identifier}>
                        {job.task_identifier}
                      </code>
                    </TableCell>

                    {/* Reliability Column */}
                    <TableCell className="py-3">
                      <ReliabilityBadge state={reliabilityState} jobId={job.id} size="sm" />
                    </TableCell>

                    {/* Health / Operational Status */}
                    <TableCell className="py-3">
                      {job.operational_status === "CRITICAL" ? (
                        <Badge variant="destructive" className="bg-destructive/10 text-destructive border-destructive/20 text-[10px]">Critical</Badge>
                      ) : job.operational_status === "DEGRADED" ? (
                        <Badge variant="warning" className="text-[10px]">Degraded</Badge>
                      ) : (
                        <Badge variant="success" className="text-[10px]">Healthy</Badge>
                      )}
                    </TableCell>

                    <TableCell className="py-3 text-sm font-medium">
                      {job.executions_count ? (job.executions_count > 999 ? (job.executions_count / 1000).toFixed(1) + 'k' : job.executions_count) : 0}
                    </TableCell>

                    <TableCell className="py-3 text-sm font-medium">
                      {job.success_rate !== null && job.success_rate !== undefined ? `${job.success_rate}%` : "—"}
                    </TableCell>

                    <TableCell className="py-3">
                      {job.verification_status === "verified" ? (
                        <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-500 font-medium">
                          <CheckCircle2 className="h-3.5 w-3.5" /> Verified
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground font-medium">
                          <XCircle className="h-3.5 w-3.5" /> Unverified
                        </span>
                      )}
                    </TableCell>

                    <TableCell className="py-3">
                      {job.status === "active" ? (
                        <Badge className="text-xs bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30">Active</Badge>
                      ) : (
                        <Badge variant="secondary" className="text-xs">Inactive</Badge>
                      )}
                    </TableCell>

                    <TableCell className="py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          className="h-8 text-xs"
                          onClick={() => setSelectedJob({ id: job.id, name: job.name })}
                        >
                          <Activity className="h-3.5 w-3.5 mr-2" /> Executions
                        </Button>

                        {canManage && (
                          <DropdownMenu>
                            <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="h-8 w-8" />}>
                              <MoreHorizontal className="h-4 w-4" />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => setEditJob(job)}>
                                <Pencil className="mr-2 h-4 w-4" /> Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                disabled={toggling === job.id}
                                onClick={async () => {
                                  setToggling(job.id);
                                  try {
                                    const newStatus = job.status === "active" ? "inactive" : "active";
                                    await updateJob(job.id, { status: newStatus });
                                    handleRefetch();
                                  } finally {
                                    setToggling(null);
                                  }
                                }}
                              >
                                {job.status === "active" ? (
                                  <><ToggleLeft className="mr-2 h-4 w-4" /> Deactivate</>
                                ) : (
                                  <><ToggleRight className="mr-2 h-4 w-4" /> Activate</>
                                )}
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => setDeleteJob(job)}>
                                <Trash2 className="mr-2 h-4 w-4" /> Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          {totalPages > 1 && (
            <div className="px-4 py-3 border-t bg-muted/10">
              <PaginationControls page={page} totalPages={totalPages} setPage={setPage} />
            </div>
          )}
        </div>
      )}

      {/* Slide-over sheet for executions */}
      <ExecutionsSheet
        jobId={selectedJob?.id ?? null}
        jobName={selectedJob?.name ?? null}
        open={!!selectedJob}
        onOpenChange={(open) => { if (!open) setSelectedJob(null); }}
      />

      {/* Modals */}
      {createOpen && (
        <JobFormModal
          open={createOpen}
          onOpenChange={setCreateOpen}
          projects={manageableProjects}
        />
      )}
      {editJob && (
        <JobFormModal
          open={!!editJob}
          onOpenChange={(open) => { if (!open) setEditJob(null); }}
          job={editJob}
        />
      )}
      {deleteJob && (
        <ConfirmDeleteJobModal
          open={!!deleteJob}
          onOpenChange={(open) => { if (!open) setDeleteJob(null); }}
          job={deleteJob}
        />
      )}
    </div>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">Loading jobs...</div>}>
      <JobsPageContent />
    </Suspense>
  );
}
