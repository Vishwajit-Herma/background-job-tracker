"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { createJob, updateJob, deleteJob, Job } from "@/lib/api/jobs";
import { ApiError } from "@/lib/api/client";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2, ShieldAlert, Trash2 } from "lucide-react";
import { Project } from "@/lib/api/projects";

function extractFieldErrors(err: ApiError): Record<string, string> {
  const fe: Record<string, string> = {};
  if (err.errors && typeof err.errors === "object") {
    for (const [k, v] of Object.entries(err.errors)) {
      if (Array.isArray(v) && typeof v[0] === "string") {
        fe[k] = v[0];
      } else if (typeof v === "string") {
        fe[k] = v;
      }
    }
  }
  return fe;
}

const jobSchema = z.object({
  project: z.number().optional(),
  name: z.string().min(1, "Name is required"),
  task_identifier: z.string().min(1, "Task identifier is required"),
  description: z.string().optional(),
});

type JobFormValues = z.infer<typeof jobSchema>;

export function JobFormModal({
  open,
  onOpenChange,
  projectId,
  projects, // for standalone page selection
  job,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId?: number; // Optional if we are in standalone mode and need to select project
  projects?: Project[];
  job?: Job;
}) {
  const queryClient = useQueryClient();
  const isEdit = !!job;
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<JobFormValues>({
    resolver: zodResolver(jobSchema),
    defaultValues: {
      project: job?.project as number ?? projectId ?? projects?.[0]?.id,
      name: job?.name ?? "",
      task_identifier: job?.task_identifier ?? "",
      description: job?.description ?? "",
    },
  });

  const onSubmit = async (values: JobFormValues) => {
    setServerError(null);
    try {
      if (isEdit) {
        await updateJob(job!.id, { name: values.name, description: values.description });
      } else {
        if (!values.project) {
          setError("project", { message: "Project is required" });
          return;
        }
        await createJob({ 
          project: values.project, 
          name: values.name, 
          task_identifier: values.task_identifier, 
          description: values.description 
        });
      }
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["jobs-paginated"] });
      reset();
      onOpenChange(false);
    } catch (e: any) {
      const err = e as ApiError;
      const fe = extractFieldErrors(err);
      if (fe.name) setError("name", { message: fe.name });
      if (fe.task_identifier) setError("task_identifier", { message: fe.task_identifier });
      if (fe.project) setError("project", { message: fe.project });
      if (!fe.name && !fe.task_identifier && !fe.project) {
        setServerError(err.message || "Something went wrong");
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Job" : "Create Job"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update the job details below."
              : "Manually register a job to monitor its executions."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {serverError && (
            <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <ShieldAlert className="h-4 w-4 shrink-0" /> {serverError}
            </div>
          )}

          {!isEdit && projects && projects.length > 0 && !projectId && (
            <div className="space-y-1">
              <label className="text-sm font-medium" htmlFor="job-project">
                Project <span className="text-destructive">*</span>
              </label>
              <select
                id="job-project"
                {...register("project", { valueAsNumber: true })}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {errors.project && (
                <p className="text-xs text-destructive">{errors.project.message}</p>
              )}
            </div>
          )}

          <div className="space-y-1">
            <label className="text-sm font-medium" htmlFor="job-name">
              Job Name <span className="text-destructive">*</span>
            </label>
            <input
              id="job-name"
              {...register("name")}
              placeholder="e.g. Generate Monthly Reports"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            {errors.name && (
              <p className="text-xs text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium" htmlFor="job-task-id">
              Task Identifier <span className="text-destructive">*</span>
            </label>
            <input
              id="job-task-id"
              {...register("task_identifier")}
              disabled={isEdit}
              placeholder="e.g. reports.tasks.generate"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
            />
            {errors.task_identifier && (
              <p className="text-xs text-destructive">{errors.task_identifier.message}</p>
            )}
            {!isEdit && (
              <p className="text-xs text-muted-foreground">
                This must exactly match the task name in your code.
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium" htmlFor="job-desc">
              Description
            </label>
            <textarea
              id="job-desc"
              {...register("description")}
              placeholder="Optional details about this job"
              className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEdit ? "Save Changes" : "Create Job"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ConfirmDeleteJobModal({
  open,
  onOpenChange,
  job,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  job: Job;
}) {
  const queryClient = useQueryClient();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async () => {
    setIsDeleting(true);
    setError(null);
    try {
      await deleteJob(job.id);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["jobs-paginated"] });
      onOpenChange(false);
    } catch (e: any) {
      setError((e as ApiError).message || "Failed to delete job.");
      setIsDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete Job</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete <strong>{job.name}</strong>? This will soft-delete the job and its executions will no longer be tracked.
          </DialogDescription>
        </DialogHeader>
        {error && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <ShieldAlert className="h-4 w-4 shrink-0" /> {error}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
            {isDeleting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="mr-2 h-4 w-4" />
            )}
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
