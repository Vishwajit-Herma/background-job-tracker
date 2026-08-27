"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getJobs, updateJob, Job } from "@/lib/api/jobs";
import { Project } from "@/lib/api/projects";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, ListChecks, CheckCircle2, XCircle, Activity, MoreHorizontal, Pencil, Trash2, ShieldOff, Plus, FolderOpen, ExternalLink, HelpCircle } from "lucide-react";
import { ExecutionsSheet } from "./executions-sheet";
import { JobFormModal, ConfirmDeleteJobModal } from "./job-modals";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Link from "next/link";
import { getProjectReliability, ReliabilityState } from "@/lib/api/reliability";
import { ReliabilityBadge } from "@/components/bjt/reliability/reliability-badge";

export function JobsPanel({ project, canManage = false }: { project: Project, canManage?: boolean }) {
  const queryClient = useQueryClient();
  const [selectedJob, setSelectedJob] = useState<{ id: number; name: string } | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editJob, setEditJob] = useState<Job | null>(null);
  const [deleteJob, setDeleteJob] = useState<Job | null>(null);
  const [toggling, setToggling] = useState<number | null>(null);

  const { data: jobs = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["jobs", project.id],
    queryFn: () => getJobs(project.id),
  });

  const { data: projectReliability } = useQuery({
    queryKey: ["project-reliability", project.id],
    queryFn: () => getProjectReliability(project.id),
  });

  const reliabilityByJobId = new Map<number, ReliabilityState>(
    (projectReliability?.jobs || []).map(j => [j.job_id, j.current_state])
  );

  return (
    <div className="border-t mt-4 pt-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <ListChecks className="h-4 w-4 text-muted-foreground" />
          Monitored Jobs
          {!isLoading && (
            <span className="text-xs text-muted-foreground font-normal">
              ({jobs.filter((j) => j.status === "active").length} active)
            </span>
          )}
        </div>
        {canManage && (
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> Create Job
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-1.5">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-8 rounded bg-muted/30 animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-xs text-destructive">
          Failed to load jobs. <button onClick={() => refetch()} className="underline">Retry</button>
        </p>
      ) : jobs.length === 0 ? (
        <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          No background jobs discovered yet.<br/>
          Ensure your application is configured with the correct API Key.
        </div>
      ) : (
        <div className="rounded-md border text-sm overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="text-xs">
                <TableHead className="h-8">Job</TableHead>
                <TableHead className="h-8" title="Schedule & runtime behavior adherence (Healthy, Missed, Stalled, Overdue).">Reliability <HelpCircle className="inline-block h-3 w-3 opacity-50 cursor-help mb-0.5" /></TableHead>
                <TableHead className="h-8" title="Real-time operational status (driven by active incidents).">Health <HelpCircle className="inline-block h-3 w-3 opacity-50 cursor-help mb-0.5" /></TableHead>
                <TableHead className="h-8">Verification</TableHead>
                <TableHead className="h-8">Executions</TableHead>
                <TableHead className="h-8">Success Rate</TableHead>
                <TableHead className="h-8 text-right"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => {
                const relState = reliabilityByJobId.get(job.id) || "HEALTHY";
                return (
                  <TableRow key={job.id} className={job.status === "inactive" ? "opacity-60" : ""}>
                    <TableCell className="py-2">
                      <div className="font-medium flex items-center gap-2">
                        <Link href={`/jobs/${job.id}`} className="hover:underline font-semibold hover:text-primary transition-colors">
                          {job.name}
                        </Link>
                        {job.status === "inactive" && <Badge variant="secondary" className="text-[9px] px-1 h-4">Inactive</Badge>}
                      </div>
                      <code className="text-[10px] text-muted-foreground bg-muted/50 px-1 py-0.5 rounded font-mono inline-block mt-0.5">
                        {job.task_identifier}
                      </code>
                      {job.description && (
                        <p className="text-[10px] text-muted-foreground truncate max-w-[200px] mt-0.5">
                          {job.description}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="py-2">
                      <ReliabilityBadge state={relState} jobId={job.id} size="sm" />
                    </TableCell>
                    <TableCell className="py-2">
                      {job.operational_status === "CRITICAL" ? (
                        <Badge variant="destructive" className="bg-destructive/10 text-destructive border-destructive/20 text-[10px]">Critical</Badge>
                      ) : job.operational_status === "DEGRADED" ? (
                        <Badge variant="warning" className="text-[10px]">Degraded</Badge>
                      ) : (
                        <Badge variant="success" className="text-[10px]">Healthy</Badge>
                      )}
                    </TableCell>
                    <TableCell className="py-2">
                      {job.verification_status === "verified" ? (
                        <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-500" title="A matching execution was received for this job.">
                          <CheckCircle2 className="h-3.5 w-3.5" /> Verified
                          <HelpCircle className="h-3 w-3 text-muted-foreground opacity-50 cursor-help" />
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground" title="No execution received yet. Check SDK integration.">
                          <XCircle className="h-3.5 w-3.5" /> Unverified
                          <HelpCircle className="h-3 w-3 opacity-50 cursor-help" />
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="py-2 text-xs font-medium">
                      {job.executions_count ? (job.executions_count > 999 ? (job.executions_count / 1000).toFixed(1) + 'k' : job.executions_count) : 0}
                    </TableCell>
                    <TableCell className="py-2 text-xs font-medium">
                      {job.success_rate !== null && job.success_rate !== undefined ? `${job.success_rate}%` : "—"}
                    </TableCell>
                    <TableCell className="py-2 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => setSelectedJob({ id: job.id, name: job.name })}
                        >
                          <Activity className="h-3 w-3 mr-1.5" /> Executions
                        </Button>
                      
                      {canManage && (
                        <DropdownMenu>
                          <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="h-7 w-7" />}>
                            <MoreHorizontal className="h-4 w-4" />
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setEditJob(job)}>
                              <Pencil className="mr-2 h-4 w-4" /> Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setSelectedJob({ id: job.id, name: job.name })}>
                              <FolderOpen className="mr-2 h-4 w-4" /> Open Executions
                            </DropdownMenuItem>
                            <DropdownMenuItem render={<a href={`/jobs/${job.id}/analytics`} />}>
                              <Activity className="mr-2 h-4 w-4" /> Analytics <ExternalLink className="h-3 w-3 ml-1 opacity-50" />
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              disabled={toggling === job.id}
                              onClick={async () => {
                                setToggling(job.id);
                                try {
                                  const newStatus = job.status === "inactive" ? "active" : "inactive";
                                  await updateJob(job.id, { status: newStatus as any });
                                  queryClient.invalidateQueries({ queryKey: ["jobs"] });
                                  queryClient.invalidateQueries({ queryKey: ["jobs-paginated"] });
                                  refetch();
                                } finally {
                                  setToggling(null);
                                }
                              }}
                            >
                              {job.status === "inactive" ? (
                                <><CheckCircle2 className="mr-2 h-4 w-4" /> Enable Job</>
                              ) : (
                                <><ShieldOff className="mr-2 h-4 w-4" /> Disable Job</>
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
          projectId={project.id}
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
