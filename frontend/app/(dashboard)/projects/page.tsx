"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTeam } from "@/components/bjt/team-provider";
import { useAuth } from "@/hooks/use-auth";
import { Team } from "@/lib/api/teams";
import {
  getProjects,
  getAPIKeys,
  createProject,
  updateProject,
  deleteProject,
  createAPIKey,
  revokeAPIKey,
  Project,
  APIKey,
  APIKeyCreated,
} from "@/lib/api/projects";
import { JobsPanel } from "@/components/bjt/jobs/jobs-panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState } from "@/components/bjt/states";
import {
  FolderOpen,
  Plus,
  MoreHorizontal,
  Pencil,
  Trash2,
  KeyRound,
  Loader2,
  ShieldAlert,
  ToggleLeft,
  ToggleRight,
  ChevronRight,
  ChevronDown,
  Copy,
  CheckCheck,
  ShieldOff,
  Eye,
  EyeOff,
  Users,
  Search,
} from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { ApiError } from "@/lib/api/client";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDebounce } from "@/hooks/use-debounce";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function canManageTeam(team: Team, isGlobalStaff: boolean): boolean {
  if (isGlobalStaff) return true;
  return team.my_role === "owner" || team.my_role === "admin";
}

// Members can only view — not edit/delete projects or see API keys
function memberRoleForProject(team: Team | undefined, isGlobalStaff: boolean): "admin" | "member" {
  if (!team) return "member";
  if (isGlobalStaff) return "admin";
  if (team.my_role === "owner" || team.my_role === "admin") return "admin";
  return "member";
}

function extractFieldErrors(err: ApiError): Record<string, string> {
  const out: Record<string, string> = {};
  if (!err.errors) return out;
  for (const [k, v] of Object.entries(err.errors)) {
    out[k] = Array.isArray(v) ? (v[0] as string) : String(v);
  }
  return out;
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={copy}
      className="inline-flex items-center rounded p-1 hover:bg-muted transition-colors"
      title="Copy"
    >
      {copied ? (
        <CheckCheck className="h-3.5 w-3.5 text-green-500" />
      ) : (
        <Copy className="h-3.5 w-3.5 text-muted-foreground" />
      )}
    </button>
  );
}

function TeamBadge({ team }: { team: Team }) {
  const roleColor: Record<string, string> = {
    owner: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20",
    admin: "bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/20",
    member: "bg-muted text-muted-foreground",
    staff: "bg-orange-500/10 text-orange-700 dark:text-orange-300 border-orange-500/20",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${
        roleColor[team.my_role ?? "member"] ?? roleColor.member
      }`}
    >
      <Users className="h-3 w-3" />
      {team.name}
      {team.my_role && (
        <span className="opacity-60">· {team.my_role}</span>
      )}
    </span>
  );
}

// ─── Project Form Modal ───────────────────────────────────────────────────────

const projectSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  description: z.string().optional(),
  team: z.number({ required_error: "Team is required" }),
});
type ProjectFormValues = z.infer<typeof projectSchema>;

function ProjectFormModal({
  open,
  onOpenChange,
  manageableTeams,
  defaultTeamId,
  project,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  manageableTeams: Team[];
  defaultTeamId?: number;
  project?: Project;
}) {
  const queryClient = useQueryClient();
  const isEdit = !!project;
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ProjectFormValues>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: project?.name ?? "",
      description: project?.description ?? "",
      team: project?.team ?? defaultTeamId ?? manageableTeams[0]?.id,
    },
  });

  const onSubmit = async (values: ProjectFormValues) => {
    setServerError(null);
    try {
      if (isEdit) {
        // team is read-only on update (backend enforces)
        await updateProject(project!.id, { name: values.name, description: values.description });
      } else {
        await createProject({ team: values.team, name: values.name, description: values.description });
      }
      // Invalidate all project queries since we might be across teams
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      reset();
      onOpenChange(false);
    } catch (e: any) {
      const err = e as ApiError;
      const fe = extractFieldErrors(err);
      if (fe.name) setError("name", { message: fe.name });
      else if (fe.team) setServerError(`Team error: ${fe.team}`);
      else setServerError(err.message || "Something went wrong");
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Project" : "Create Project"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update the project details below."
              : "Set up a new project to start tracking background jobs."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {serverError && (
            <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <ShieldAlert className="h-4 w-4 shrink-0" /> {serverError}
            </div>
          )}

          {/* Team selector — only on create */}
          {!isEdit && (
            <div className="space-y-1">
              <label className="text-sm font-medium" htmlFor="proj-team">
                Team <span className="text-destructive">*</span>
              </label>
              <select
                id="proj-team"
                {...register("team", { valueAsNumber: true })}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {manageableTeams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.my_role})
                  </option>
                ))}
              </select>
              {errors.team && (
                <p className="text-xs text-destructive">{errors.team.message}</p>
              )}
              <p className="text-xs text-muted-foreground">
                Only teams where you are Admin or Owner are shown.
              </p>
            </div>
          )}

          <div className="space-y-1">
            <label className="text-sm font-medium" htmlFor="proj-name">
              Project Name <span className="text-destructive">*</span>
            </label>
            <input
              id="proj-name"
              {...register("name")}
              placeholder="e.g. Production API"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            {errors.name && (
              <p className="text-xs text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium" htmlFor="proj-desc">
              Description{" "}
              <span className="text-muted-foreground">(optional)</span>
            </label>
            <textarea
              id="proj-desc"
              {...register("description")}
              rows={3}
              placeholder="What does this project monitor?"
              className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEdit ? "Save Changes" : "Create Project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─── Confirm Delete Modal ─────────────────────────────────────────────────────

function ConfirmDeleteModal({
  open,
  onOpenChange,
  project,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  project: Project;
}) {
  const queryClient = useQueryClient();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async () => {
    setIsDeleting(true);
    setError(null);
    try {
      await deleteProject(project.id);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      onOpenChange(false);
    } catch (e: any) {
      setError((e as ApiError).message || "Failed to delete project.");
      setIsDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete Project</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete{" "}
            <strong>{project.name}</strong>? This soft-deletes it and can be
            restored from the admin panel.
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

// ─── Create API Key Modal ─────────────────────────────────────────────────────

function CreateAPIKeyModal({
  open,
  onOpenChange,
  projectId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: number;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdKey, setCreatedKey] = useState<APIKeyCreated | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setNameError("Name is required");
      return;
    }
    setNameError(null);
    setServerError(null);
    setIsSubmitting(true);
    try {
      const key = await createAPIKey(projectId, name.trim());
      setCreatedKey(key);
      queryClient.invalidateQueries({ queryKey: ["api-keys", projectId] });
    } catch (err: any) {
      const e = err as ApiError;
      const nameErr = e.errors?.name;
      if (nameErr)
        setNameError(Array.isArray(nameErr) ? (nameErr[0] as string) : String(nameErr));
      else setServerError(e.message || "Failed to create API key");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setName("");
    setNameError(null);
    setServerError(null);
    setCreatedKey(null);
    setShowRaw(false);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg">
        {!createdKey ? (
          <>
            <DialogHeader>
              <DialogTitle>Generate API Key</DialogTitle>
              <DialogDescription>
                Name this key (e.g. "Production Server"). The raw key is shown
                only once after creation.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4">
              {serverError && (
                <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  <ShieldAlert className="h-4 w-4 shrink-0" /> {serverError}
                </div>
              )}
              <div className="space-y-1">
                <label className="text-sm font-medium">Key Name</label>
                <input
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Production Worker"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
                {nameError && (
                  <p className="text-xs text-destructive">{nameError}</p>
                )}
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Generate
                </Button>
              </DialogFooter>
            </form>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCheck className="h-5 w-5" /> API Key Created
              </DialogTitle>
              <DialogDescription>
                Copy your key now.{" "}
                <strong>It will not be shown again.</strong>
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="rounded-lg border bg-muted/40 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Your API Key
                  </span>
                  <button
                    onClick={() => setShowRaw(!showRaw)}
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                  >
                    {showRaw ? (
                      <EyeOff className="h-3.5 w-3.5" />
                    ) : (
                      <Eye className="h-3.5 w-3.5" />
                    )}
                    {showRaw ? "Hide" : "Reveal"}
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 break-all text-sm font-mono">
                    {showRaw
                      ? createdKey.key
                      : `${createdKey.key_prefix}${"•".repeat(20)}`}
                  </code>
                  <CopyButton value={createdKey.key} />
                </div>
              </div>
              <div className="rounded-md border border-yellow-200 bg-yellow-50/50 dark:border-yellow-900/40 dark:bg-yellow-900/10 px-4 py-3 text-sm text-yellow-800 dark:text-yellow-300">
                ⚠️ Store this key securely (e.g. environment variable). It
                cannot be recovered.
              </div>
            </div>
            <DialogFooter>
              <Button onClick={handleClose}>Done</Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─── Revoke Key Modal ─────────────────────────────────────────────────────────

function RevokeKeyModal({
  open,
  onOpenChange,
  apiKey,
  projectId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiKey: APIKey;
  projectId: number;
}) {
  const queryClient = useQueryClient();
  const [isRevoking, setIsRevoking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRevoke = async () => {
    setIsRevoking(true);
    setError(null);
    try {
      await revokeAPIKey(projectId, apiKey.id);
      queryClient.invalidateQueries({ queryKey: ["api-keys", projectId] });
      onOpenChange(false);
    } catch (e: any) {
      setError((e as ApiError).message || "Failed to revoke key.");
      setIsRevoking(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Revoke API Key</DialogTitle>
          <DialogDescription>
            Revoking <strong>{apiKey.name}</strong> (
            <code className="text-xs">{apiKey.key_prefix}...</code>) will
            immediately block all requests using it. This cannot be undone.
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
          <Button variant="destructive" onClick={handleRevoke} disabled={isRevoking}>
            {isRevoking ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <ShieldOff className="mr-2 h-4 w-4" />
            )}
            Revoke
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── API Keys Panel ───────────────────────────────────────────────────────────

function APIKeysPanel({ project, canManage }: { project: Project; canManage: boolean }) {
  const [createOpen, setCreateOpen] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<APIKey | null>(null);

  const { data: keys = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["api-keys", project.id],
    queryFn: () => getAPIKeys(project.id),
  });

  return (
    <div className="border-t mt-4 pt-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <KeyRound className="h-4 w-4 text-muted-foreground" />
          API Keys
          {!isLoading && (
            <span className="text-xs text-muted-foreground font-normal">
              ({keys.filter((k) => !k.is_revoked).length} active)
            </span>
          )}
        </div>
        {project.status === "active" && canManage && (
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="h-3 w-3 mr-1" /> New Key
          </Button>
        )}
      </div>

      {project.status === "inactive" && canManage && (
        <p className="text-xs text-muted-foreground italic mb-2">
          Activate this project to generate API keys.
        </p>
      )}

      {isLoading ? (
        <div className="space-y-1.5">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-8 rounded bg-muted/30 animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-xs text-destructive">
          Failed to load keys (admin/owner required).{" "}
          <button onClick={() => refetch()} className="underline">
            Retry
          </button>
        </p>
      ) : keys.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">
          No API keys yet. Generate one to connect your application.
        </p>
      ) : (
        <div className="rounded-md border text-sm">
          <Table>
            <TableHeader>
              <TableRow className="text-xs">
                <TableHead className="h-8">Name</TableHead>
                <TableHead className="h-8">Prefix</TableHead>
                <TableHead className="h-8">Status</TableHead>
                <TableHead className="h-8">Created</TableHead>
                <TableHead className="h-8 text-right"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {keys.map((key) => (
                <TableRow key={key.id} className={key.is_revoked ? "opacity-50" : ""}>
                  <TableCell className="py-2 font-medium">{key.name}</TableCell>
                  <TableCell className="py-2">
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                      {key.key_prefix}...
                    </code>
                  </TableCell>
                  <TableCell className="py-2">
                    {key.is_revoked ? (
                      <Badge variant="destructive" className="text-xs">
                        Revoked
                      </Badge>
                    ) : (
                      <Badge className="text-xs bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30">
                        Active
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="py-2 text-xs text-muted-foreground">
                    {new Date(key.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="py-2 text-right">
                    {!key.is_revoked && canManage && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs text-destructive hover:text-destructive hover:bg-destructive/10 px-2"
                        onClick={() => setRevokeTarget(key)}
                      >
                        <ShieldOff className="h-3 w-3 mr-1" /> Revoke
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {createOpen && (
        <CreateAPIKeyModal
          open={createOpen}
          onOpenChange={setCreateOpen}
          projectId={project.id}
        />
      )}
      {revokeTarget && (
        <RevokeKeyModal
          open={!!revokeTarget}
          onOpenChange={(o) => {
            if (!o) setRevokeTarget(null);
          }}
          apiKey={revokeTarget}
          projectId={project.id}
        />
      )}
    </div>
  );
}

// ─── Project Row ──────────────────────────────────────────────────────────────

function ProjectRow({
  project,
  teamMap,
  manageableTeams,
  defaultExpanded,
}: {
  project: Project;
  teamMap: Map<number, Team>;
  manageableTeams: Team[];
  defaultExpanded: boolean;
}) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const team = teamMap.get(project.team);
  const isGlobalStaff = user?.is_staff ?? false;
  const userRole = memberRoleForProject(team, isGlobalStaff);
  const canManage = userRole === "admin";
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [activeTab, setActiveTab] = useState<"jobs" | "keys">("jobs");
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [toggling, setToggling] = useState(false);

  const handleToggleStatus = async () => {
    setToggling(true);
    try {
      const newStatus = project.status === "active" ? "inactive" : "active";
      await updateProject(project.id, { status: newStatus });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    } catch {}
    setToggling(false);
  };

  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4">
        {/* Expand chevron */}
        <button
          onClick={() => setExpanded((e) => !e)}
          className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>

        {/* Status dot */}
        <div
          className={`h-2.5 w-2.5 rounded-full shrink-0 ${
            project.status === "active"
              ? "bg-green-500"
              : "bg-muted-foreground/40"
          }`}
        />

        {/* Name + Team badge */}
        <div className="flex-1 min-w-0">
          <button
            onClick={() => setExpanded((e) => !e)}
            className="text-left w-full"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-base">{project.name}</span>
              {team && <TeamBadge team={team} />}
            </div>
            {project.description && (
              <p className="text-sm text-muted-foreground mt-0.5 truncate">
                {project.description}
              </p>
            )}
          </button>
        </div>

        {/* Created date */}
        <span className="text-xs text-muted-foreground hidden md:block shrink-0">
          {new Date(project.created_at).toLocaleDateString()}
        </span>

        {/* Actions menu — admins/owners only */}
        {canManage && (
          <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0"
              />
            }
          >
            <MoreHorizontal className="h-4 w-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setEditOpen(true)}>
              <Pencil className="mr-2 h-4 w-4" /> Edit
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={handleToggleStatus}
              disabled={toggling}
            >
              {project.status === "active" ? (
                <>
                  <ToggleLeft className="mr-2 h-4 w-4" /> Deactivate
                </>
              ) : (
                <>
                  <ToggleRight className="mr-2 h-4 w-4" /> Activate
                </>
              )}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 className="mr-2 h-4 w-4" /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        )}
      </div>

      {/* Expandable Panel */}
      {expanded && (
        <div className="px-5 pb-5">
          {canManage ? (
            <div className="border-t mt-4 pt-4">
              <div className="flex space-x-1 border-b mb-4">
                <button
                  onClick={() => setActiveTab("jobs")}
                  className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                    activeTab === "jobs"
                      ? "border-primary text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Jobs
                </button>
                <button
                  onClick={() => setActiveTab("keys")}
                  className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                    activeTab === "keys"
                      ? "border-primary text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  API Keys
                </button>
              </div>
              
              {activeTab === "jobs" && <JobsPanel project={project} canManage={canManage} />}
              {activeTab === "keys" && <APIKeysPanel project={project} canManage={canManage} />}
            </div>
          ) : (
            <JobsPanel project={project} canManage={canManage} />
          )}
        </div>
      )}

      {editOpen && (
        <ProjectFormModal
          open={editOpen}
          onOpenChange={setEditOpen}
          manageableTeams={manageableTeams}
          defaultTeamId={project.team}
          project={project}
        />
      )}
      {deleteOpen && (
        <ConfirmDeleteModal
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          project={project}
        />
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ProjectsPage() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const targetProjectId = searchParams?.get("project_id");
  const { teams, activeTeam, isLoading: isTeamLoading } = useTeam();
  const [createOpen, setCreateOpen] = useState(false);
  const [teamFilter, setTeamFilter] = useState<number | "all">("all");

  const isGlobalStaff = user?.is_staff ?? false;

  // Teams where user can manage (create projects)
  const manageableTeams = teams.filter((t) => canManageTeam(t, isGlobalStaff));

  // Build a fast lookup map: team.id → Team
  const teamMap = new Map(teams.map((t) => [t.id, t]));

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 500);
  const [ordering, setOrdering] = useState("-created_at");

  // Fetch ALL projects across all member teams (backend handles isolation)
  const { data: allProjects = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["projects", "all"],
    queryFn: () => getProjects(), // no team filter = all accessible projects
    enabled: teams.length > 0,
  });

  // Client-side filter by selected team, search text, and then sort
  const projects = allProjects
    .filter((p) => teamFilter === "all" || p.team === teamFilter)
    .filter((p) => {
      if (!debouncedSearch) return true;
      const s = debouncedSearch.toLowerCase();
      return p.name.toLowerCase().includes(s) || (p.description && p.description.toLowerCase().includes(s));
    })
    .sort((a, b) => {
      if (ordering === "name") return a.name.localeCompare(b.name);
      if (ordering === "created_at") return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      if (ordering === "-created_at") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      return 0;
    });

  if (isTeamLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (teams.length === 0) {
    return (
      <div className="flex-1 space-y-4 p-8 pt-6">
        <h2 className="text-3xl font-bold tracking-tight">Projects</h2>
        <EmptyState
          title="No teams yet"
          description="Join or create a team first to manage projects."
          icon={<FolderOpen className="h-10 w-10 text-muted-foreground" />}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Projects</h2>
          <p className="text-muted-foreground mt-1">
            Monitoring projects across{" "}
            <span className="font-medium text-foreground">{teams.length}</span>{" "}
            team{teams.length !== 1 ? "s" : ""}
            {!isLoading && allProjects.length > 0 && (
              <span className="ml-2 text-xs">
                — {allProjects.filter((p) => p.status === "active").length}{" "}
                active / {allProjects.length} total
              </span>
            )}
          </p>
        </div>
        {manageableTeams.length > 0 && (
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> New Project
          </Button>
        )}
      </div>

      {/* Team filter tabs */}
      {teams.length > 1 && (
        <div className="flex gap-1 border-b overflow-x-auto">
          <button
            onClick={() => setTeamFilter("all")}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
              teamFilter === "all"
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            All Teams
          </button>
          {teams.map((t) => (
            <button
              key={t.id}
              onClick={() => setTeamFilter(t.id)}
              className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
                teamFilter === t.id
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.name}
              {t.my_role && (
                <span className="ml-1.5 text-xs opacity-60">({t.my_role})</span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Search and Sort */}
      {allProjects.length > 0 && (
        <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-card p-3 rounded-md border mt-4">
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search projects..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
          <div className="w-full sm:w-48">
            <Select value={ordering} onValueChange={setOrdering}>
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
      )}

      {/* Content */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-16 rounded-xl border bg-muted/30 animate-pulse"
            />
          ))}
        </div>
      ) : isError ? (
        <ErrorState
          title="Failed to load projects"
          description="There was a problem fetching projects."
          retry={() => refetch()}
        />
      ) : projects.length === 0 ? (
        <EmptyState
          title={teamFilter === "all" ? "No projects yet" : "No projects in this team"}
          description={
            manageableTeams.length > 0
              ? "Create your first project to start tracking background jobs. Each project gets its own API keys."
              : "You are a member of these teams but do not have permission to create projects. Contact an Admin or Owner."
          }
          icon={<FolderOpen className="h-10 w-10 text-muted-foreground" />}
          action={
            manageableTeams.length > 0 ? (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="mr-2 h-4 w-4" /> Create First Project
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-3">
          {projects.map((project, i) => (
            <ProjectRow
              key={project.id}
              project={project}
              teamMap={teamMap}
              manageableTeams={manageableTeams}
              defaultExpanded={targetProjectId ? project.id === Number(targetProjectId) : i === 0}
            />
          ))}
        </div>
      )}

      {createOpen && manageableTeams.length > 0 && (
        <ProjectFormModal
          open={createOpen}
          onOpenChange={setCreateOpen}
          manageableTeams={manageableTeams}
          defaultTeamId={
            typeof teamFilter === "number" ? teamFilter : activeTeam?.id
          }
        />
      )}
    </div>
  );
}
