"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getJobs, Job } from "@/lib/api/jobs";
import { Project } from "@/lib/api/projects";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, ListChecks, CheckCircle2, XCircle, Activity, MoreHorizontal, Pencil, Trash2, ToggleLeft, ToggleRight, Plus } from "lucide-react";
import { ExecutionsSheet } from "./executions-sheet";
import { JobFormModal, ConfirmDeleteJobModal } from "./job-modals";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { updateJob } from "@/lib/api/jobs";

export function JobsPanel({ project, canManage = false }: { project: Project, canManage?: boolean }) {
  const [selectedJob, setSelectedJob] = useState<{ id: number; name: string } | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editJob, setEditJob] = useState<Job | null>(null);
  const [deleteJob, setDeleteJob] = useState<Job | null>(null);
  const [toggling, setToggling] = useState<number | null>(null);

  const { data: jobs = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["jobs", project.id],
    queryFn: () => getJobs(project.id),
  });

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
        <div className="rounded-md border text-sm">
          <Table>
            <TableHeader>
              <TableRow className="text-xs">
                <TableHead className="h-8">Job Name</TableHead>
                <TableHead className="h-8">Task Identifier</TableHead>
                <TableHead className="h-8">Verification</TableHead>
                <TableHead className="h-8">Status</TableHead>
                <TableHead className="h-8 text-right"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job.id} className={job.status === "inactive" ? "opacity-60" : ""}>
                  <TableCell className="py-2 font-medium">
                    {job.name}
                    {job.description && (
                      <p className="text-[10px] text-muted-foreground truncate max-w-[200px] mt-0.5">
                        {job.description}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="py-2">
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono break-all max-w-[200px] inline-block truncate" title={job.task_identifier}>
                      {job.task_identifier}
                    </code>
                  </TableCell>
                  <TableCell className="py-2">
                    {job.verification_status === "verified" ? (
                      <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-500">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Verified
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <XCircle className="h-3.5 w-3.5" /> Unverified
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="py-2">
                    {job.status === "active" ? (
                      <Badge className="text-[10px] bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30">Active</Badge>
                    ) : (
                      <Badge variant="secondary" className="text-[10px]">Inactive</Badge>
                    )}
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
                            <DropdownMenuItem
                              disabled={toggling === job.id}
                              onClick={async () => {
                                setToggling(job.id);
                                try {
                                  const newStatus = job.status === "active" ? "inactive" : "active";
                                  await updateJob(job.id, { status: newStatus });
                                  refetch();
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
              ))}
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
