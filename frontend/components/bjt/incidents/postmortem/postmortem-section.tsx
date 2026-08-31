"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPostmortem,
  savePostmortem,
  submitPostmortemReview,
  completePostmortemReview,
  createActionItem,
  updateActionItem,
  deleteActionItem,
  Postmortem,
  PostmortemActionItem,
  ActionItemStatus,
} from "@/lib/api/incidents";
import { TeamMember } from "@/lib/api/teams";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { toastError, toastSuccess, toastWarning } from "@/lib/toast";

function getMemberDisplayName(m: TeamMember): string {
  if (!m) return "Unknown";
  if (m.user) {
    const name = [m.user.first_name, m.user.last_name].filter(Boolean).join(" ");
    if (name) return name;
    if (m.user.email) return m.user.email;
  }
  return `Member #${m.id}`;
}
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Loader2,
  FileText,
  CheckCircle2,
  Send,
  Plus,
  Pencil,
  Trash2,
  Clock,
  User,
  AlertCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

// ─── Status Badge ─────────────────────────────────────────────────────────────

function PostmortemStatusBadge({ status }: { status: string }) {
  switch (status) {
    case "PENDING":
      return (
        <Badge variant="outline" className="text-amber-600 border-amber-500/30 bg-amber-500/10">
          Draft
        </Badge>
      );
    case "IN_REVIEW":
      return (
        <Badge className="bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20">
          In Review
        </Badge>
      );
    case "COMPLETED":
      return (
        <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20">
          Completed
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

// ─── Action Item Row ──────────────────────────────────────────────────────────

// ─── Action Item Row ──────────────────────────────────────────────────────────

function ActionItemStatusBadge({ status }: { status: ActionItemStatus }) {
  switch (status) {
    case "COMPLETED":
      return (
        <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-[10px] px-1.5 py-0">
          Done
        </Badge>
      );
    case "IN_PROGRESS":
      return (
        <Badge className="bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20 text-[10px] px-1.5 py-0">
          In Progress
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="text-muted-foreground text-[10px] px-1.5 py-0">
          Pending
        </Badge>
      );
  }
}

interface ActionItemRowProps {
  item: PostmortemActionItem;
  incidentId: number;
  canEdit: boolean;
  isReadOnly: boolean;
  teamMembers: Array<any>;
}

function ActionItemRow({ item, incidentId, canEdit, isReadOnly, teamMembers }: ActionItemRowProps) {
  const { user } = useAuth();
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(item.title);
  const [editOwner, setEditOwner] = useState<number | null>(item.owner ?? null);
  const [editStatus, setEditStatus] = useState<ActionItemStatus>(item.status);
  const [editDueDate, setEditDueDate] = useState<string>(item.due_date ? item.due_date.slice(0, 10) : "");
  const queryClient = useQueryClient();

  const currentUserId = user?.id || (user as any)?.pk;
  const currentMember = teamMembers.find(
    (m) => m.user?.id === currentUserId || (m.user as any)?.pk === currentUserId || (m as any).user_id === currentUserId
  );
  const isAssignedOwner = Boolean(
    item.owner &&
      (currentMember ? item.owner === currentMember.id : item.owner_name === (user?.email || user?.first_name))
  );
  const canUpdateStatus = !isReadOnly && (canEdit || isAssignedOwner);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["postmortem", incidentId] });
  };

  const statusOnlyMutation = useMutation({
    mutationFn: (newStatus: ActionItemStatus) =>
      updateActionItem(incidentId, item.id, { status: newStatus }),
    onSuccess: () => {
      toastSuccess("Status Updated");
      invalidate();
    },
    onError: (err: any) => toastError("Failed to update status", err),
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updateActionItem(incidentId, item.id, {
        title: editTitle,
        owner: editOwner,
        status: editStatus,
        due_date: editDueDate || null,
      }),
    onSuccess: () => {
      toastSuccess("Action item updated");
      invalidate();
      setEditing(false);
    },
    onError: (err: any) => toastError("Failed to update action item", err),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteActionItem(incidentId, item.id),
    onSuccess: () => {
      toastSuccess("Action item deleted");
      invalidate();
    },
    onError: (err: any) => toastError("Failed to delete action item", err),
  });

  if (editing) {
    return (
      <div className="p-3 rounded-lg border bg-muted/20 space-y-2.5">
        <input
          className="w-full text-sm bg-transparent border-b border-input focus:outline-none focus:border-primary px-1 font-medium"
          placeholder="Action item title…"
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          autoFocus
        />
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <div className="flex items-center gap-1">
            <User className="h-3.5 w-3.5 text-muted-foreground" />
            <select
              className="border border-input bg-background rounded px-2 py-1 text-xs"
              value={editOwner ?? ""}
              onChange={(e) => setEditOwner(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Unassigned</option>
              {teamMembers.map((m: TeamMember) => (
                <option key={m.id} value={m.id}>
                  {getMemberDisplayName(m)}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-1">
            <Clock className="h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="date"
              className="border border-input bg-background rounded px-2 py-1 text-xs"
              value={editDueDate}
              onChange={(e) => setEditDueDate(e.target.value)}
            />
          </div>

          <select
            className="border border-input bg-background rounded px-2 py-1 text-xs ml-auto"
            value={editStatus}
            onChange={(e) => setEditStatus(e.target.value as ActionItemStatus)}
          >
            <option value="PENDING">Pending</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="COMPLETED">Completed</option>
          </select>
        </div>

        <div className="flex justify-end gap-1.5 pt-1">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-xs"
            onClick={() => setEditing(false)}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            className="h-7 text-xs"
            disabled={!editTitle.trim() || updateMutation.isPending}
            onClick={() => updateMutation.mutate()}
          >
            {updateMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Save"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 p-2.5 rounded-lg border hover:bg-muted/20 transition-colors group">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className={`text-sm ${item.status === "COMPLETED" ? "line-through text-muted-foreground" : ""}`}>
            {item.title}
          </p>
          {canUpdateStatus ? (
            <select
              className="text-[11px] border border-input bg-background rounded px-1.5 py-0.5 font-medium cursor-pointer"
              value={item.status}
              disabled={statusOnlyMutation.isPending}
              onChange={(e) => statusOnlyMutation.mutate(e.target.value as ActionItemStatus)}
            >
              <option value="PENDING">Pending</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="COMPLETED">Completed</option>
            </select>
          ) : (
            <ActionItemStatusBadge status={item.status} />
          )}
        </div>
        <div className="flex items-center gap-3 mt-0.5 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <User className="h-3 w-3 text-muted-foreground/70" />
            {item.owner_name ? (
              <strong className="text-foreground font-normal">{item.owner_name}</strong>
            ) : (
              <span className="italic text-muted-foreground/60">Unassigned</span>
            )}
          </span>
          {item.due_date && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3 text-muted-foreground/70" /> {new Date(item.due_date).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>
      {canEdit && (
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0"
            onClick={() => setEditing(true)}
            title="Edit / Assign"
          >
            <Pencil className="h-3 w-3" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0 text-destructive hover:text-destructive"
            disabled={deleteMutation.isPending}
            onClick={() => deleteMutation.mutate()}
            title="Delete Action Item"
          >
            {deleteMutation.isPending ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="h-3 w-3" />
            )}
          </Button>
        </div>
      )}
    </div>
  );
}

// ─── Postmortem Form Field ────────────────────────────────────────────────────

function FormField({
  label,
  value,
  onChange,
  disabled,
  placeholder,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-semibold uppercase text-muted-foreground tracking-wide">{label}</label>
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={placeholder || `Describe ${label.toLowerCase()}…`}
        rows={rows}
        className="resize-none text-sm"
      />
    </div>
  );
}

// ─── Main Postmortem Section ──────────────────────────────────────────────────

interface PostmortemSectionProps {
  incidentId: number;
  teamId?: number;
  hasManagePermission?: boolean;
}

export function PostmortemSection({ incidentId, teamId, hasManagePermission = false }: PostmortemSectionProps) {
  const queryClient = useQueryClient();
  const [newItemTitle, setNewItemTitle] = useState("");
  const [newItemOwner, setNewItemOwner] = useState<number | null>(null);
  const [newItemDueDate, setNewItemDueDate] = useState("");
  const [showAddItem, setShowAddItem] = useState(false);

  const { data: teamMembers = [] } = useQuery({
    queryKey: ["team-members", teamId],
    queryFn: () => import("@/lib/api/teams").then((m) => m.getTeamMembers(teamId!)),
    enabled: !!teamId,
  });

  const { data: postmortem, isLoading } = useQuery({
    queryKey: ["postmortem", incidentId],
    queryFn: () => getPostmortem(incidentId),
    retry: (count, err: any) => {
      if (err?.response?.status === 404) return false;
      return count < 2;
    },
  });

  // Local draft form state (mirrors postmortem fields)
  const [draft, setDraft] = useState<Partial<Postmortem>>({});
  const [isDirty, setIsDirty] = useState(false);

  const currentValues = {
    summary: draft.summary ?? postmortem?.summary ?? "",
    impact_summary: draft.impact_summary ?? postmortem?.impact_summary ?? "",
    probable_cause: draft.probable_cause ?? postmortem?.probable_cause ?? "",
    confirmed_root_cause: draft.confirmed_root_cause ?? postmortem?.confirmed_root_cause ?? "",
    resolution: draft.resolution ?? postmortem?.resolution ?? "",
    contributing_factors: draft.contributing_factors ?? postmortem?.contributing_factors ?? "",
    timeline: draft.timeline ?? postmortem?.timeline ?? "",
    what_went_well: draft.what_went_well ?? postmortem?.what_went_well ?? "",
    what_went_wrong: draft.what_went_wrong ?? postmortem?.what_went_wrong ?? "",
  };

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["postmortem", incidentId] });
    queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
    queryClient.invalidateQueries({ queryKey: ["incident-knowledge", incidentId] });
  };

  const saveMutation = useMutation({
    mutationFn: () => savePostmortem(incidentId, { ...currentValues, status: postmortem?.status }),
    onSuccess: () => {
      toastSuccess("Postmortem Draft Saved");
      invalidate();
      setIsDirty(false);
      setDraft({});
    },
    onError: (err: any) => toastError("Failed to save postmortem", err),
  });

  const submitMutation = useMutation({
    mutationFn: () => submitPostmortemReview(incidentId),
    onSuccess: () => {
      toastSuccess("Postmortem Submitted for Review");
      invalidate();
    },
    onError: (err: any) => toastError("Failed to submit postmortem", err),
  });

  const completeMutation = useMutation({
    mutationFn: () => completePostmortemReview(incidentId),
    onSuccess: () => {
      toastSuccess("Postmortem Review Completed");
      invalidate();
    },
    onError: (err: any) => toastError("Failed to complete postmortem review", err),
  });

  const addItemMutation = useMutation({
    mutationFn: () =>
      createActionItem(incidentId, {
        title: newItemTitle,
        owner: newItemOwner,
        due_date: newItemDueDate || null,
      }),
    onSuccess: () => {
      toastSuccess("Action Item Added");
      invalidate();
      setNewItemTitle("");
      setNewItemOwner(null);
      setNewItemDueDate("");
      setShowAddItem(false);
    },
    onError: (err: any) => toastError("Failed to add action item", err),
  });

  async function handleSubmitReview() {
    if (!currentValues.summary.trim()) {
      toastWarning("Validation Error", "Postmortem must contain a Summary before submitting for review.");
      return;
    }
    if (isDirty) {
      try {
        await saveMutation.mutateAsync();
      } catch (e) {
        return;
      }
    }
    submitMutation.mutate();
  }

  async function handleCompleteReview() {
    if (!currentValues.summary.trim()) {
      toastWarning("Validation Error", "Postmortem must contain a Summary before completing review.");
      return;
    }
    if (isDirty) {
      try {
        await saveMutation.mutateAsync();
      } catch (e) {
        return;
      }
    }
    completeMutation.mutate();
  }

  const isReadOnly = postmortem?.status === "COMPLETED";
  const isInReview = postmortem?.status === "IN_REVIEW";

  function update(field: keyof typeof currentValues, value: string) {
    setDraft((d) => ({ ...d, [field]: value }));
    setIsDirty(true);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-40 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading postmortem…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <FileText className="h-5 w-5 text-primary" />
          <h3 className="font-semibold">Postmortem</h3>
          {postmortem && <PostmortemStatusBadge status={postmortem.status} />}
        </div>

        <div className="flex items-center gap-2">
          {isDirty && !isReadOnly && (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              disabled={saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              {saveMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              Save Draft
            </Button>
          )}

          {postmortem?.status === "PENDING" && (
            <Button
              size="sm"
              className="h-7 text-xs gap-1"
              disabled={submitMutation.isPending || saveMutation.isPending}
              onClick={handleSubmitReview}
            >
              {submitMutation.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Send className="h-3 w-3" />
              )}
              Submit for Review
            </Button>
          )}

          {postmortem?.status === "IN_REVIEW" && (
            <>
              {hasManagePermission ? (
                <Button
                  size="sm"
                  className="h-7 text-xs gap-1 bg-emerald-600 hover:bg-emerald-700"
                  disabled={completeMutation.isPending || saveMutation.isPending}
                  onClick={handleCompleteReview}
                >
                  {completeMutation.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3 w-3" />
                  )}
                  Complete Review
                </Button>
              ) : (
                <span className="text-xs text-blue-600 bg-blue-500/10 border border-blue-500/20 px-2.5 py-1 rounded-md font-medium">
                  Awaiting Admin Sign-off
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {/* Review meta */}
      {postmortem?.reviewed_by_name && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          Reviewed by <span className="font-medium text-foreground">{postmortem.reviewed_by_name}</span>
          {postmortem.reviewed_at && (
            <span>on {new Date(postmortem.reviewed_at).toLocaleString()}</span>
          )}
        </div>
      )}

      {isReadOnly && (
        <div className="flex items-center gap-2 text-xs p-3 rounded-lg bg-muted/30 border">
          <AlertCircle className="h-4 w-4 text-muted-foreground" />
          This postmortem is completed and read-only.
        </div>
      )}

      {/* Form sections */}
      <div className="space-y-4">
        <FormField
          label="Summary"
          value={currentValues.summary}
          onChange={(v) => update("summary", v)}
          disabled={isReadOnly || isInReview}
          rows={3}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            label="Impact Summary"
            value={currentValues.impact_summary}
            onChange={(v) => update("impact_summary", v)}
            disabled={isReadOnly || isInReview}
          />
          <FormField
            label="Probable Cause"
            value={currentValues.probable_cause}
            onChange={(v) => update("probable_cause", v)}
            disabled={isReadOnly || isInReview}
          />
        </div>
        <FormField
          label="Confirmed Root Cause"
          value={currentValues.confirmed_root_cause}
          onChange={(v) => update("confirmed_root_cause", v)}
          disabled={isReadOnly || isInReview}
        />
        <FormField
          label="Resolution"
          value={currentValues.resolution}
          onChange={(v) => update("resolution", v)}
          disabled={isReadOnly || isInReview}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            label="What Went Well"
            value={currentValues.what_went_well}
            onChange={(v) => update("what_went_well", v)}
            disabled={isReadOnly || isInReview}
          />
          <FormField
            label="What Went Wrong"
            value={currentValues.what_went_wrong}
            onChange={(v) => update("what_went_wrong", v)}
            disabled={isReadOnly || isInReview}
          />
        </div>
        <FormField
          label="Contributing Factors"
          value={currentValues.contributing_factors}
          onChange={(v) => update("contributing_factors", v)}
          disabled={isReadOnly || isInReview}
        />
        <FormField
          label="Timeline of Events"
          value={currentValues.timeline}
          onChange={(v) => update("timeline", v)}
          disabled={isReadOnly || isInReview}
          rows={4}
          placeholder="Describe the sequence of events that led to and resolved this incident…"
        />
      </div>

      {/* Action Items */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary" /> Action Items
          </h4>
          {!isReadOnly && hasManagePermission && (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs gap-1"
              onClick={() => setShowAddItem(true)}
            >
              <Plus className="h-3 w-3" /> Add Item
            </Button>
          )}
        </div>

        {showAddItem && (
          <div className="p-3 rounded-lg border bg-muted/20 space-y-2.5">
            <input
              className="w-full text-sm bg-transparent border-b border-input focus:outline-none focus:border-primary px-1 font-medium"
              placeholder="Action item title…"
              value={newItemTitle}
              onChange={(e) => setNewItemTitle(e.target.value)}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter" && newItemTitle.trim()) addItemMutation.mutate();
                if (e.key === "Escape") {
                  setShowAddItem(false);
                  setNewItemTitle("");
                  setNewItemOwner(null);
                  setNewItemDueDate("");
                }
              }}
            />
            <div className="flex items-center gap-2 flex-wrap text-xs">
              <div className="flex items-center gap-1">
                <User className="h-3.5 w-3.5 text-muted-foreground" />
                <select
                  className="border border-input bg-background rounded px-2 py-1 text-xs"
                  value={newItemOwner ?? ""}
                  onChange={(e) => setNewItemOwner(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">Assign to team member…</option>
                  {teamMembers.map((m: TeamMember) => (
                    <option key={m.id} value={m.id}>
                      {getMemberDisplayName(m)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                <input
                  type="date"
                  className="border border-input bg-background rounded px-2 py-1 text-xs"
                  value={newItemDueDate}
                  onChange={(e) => setNewItemDueDate(e.target.value)}
                />
              </div>
            </div>

            <div className="flex justify-end gap-1.5 pt-1">
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs"
                onClick={() => {
                  setShowAddItem(false);
                  setNewItemTitle("");
                  setNewItemOwner(null);
                  setNewItemDueDate("");
                }}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                className="h-7 text-xs"
                disabled={!newItemTitle.trim() || addItemMutation.isPending}
                onClick={() => addItemMutation.mutate()}
              >
                {addItemMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Add Action Item"}
              </Button>
            </div>
          </div>
        )}

        {postmortem?.action_items && postmortem.action_items.length > 0 ? (
          <div className="space-y-1.5">
            {postmortem.action_items.map((item) => (
              <ActionItemRow
                key={item.id}
                item={item}
                incidentId={incidentId}
                canEdit={!isReadOnly && hasManagePermission}
                isReadOnly={isReadOnly}
                teamMembers={teamMembers}
              />
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center h-16 text-sm text-muted-foreground italic border border-dashed rounded-lg">
            No action items yet.
          </div>
        )}
      </div>
    </div>
  );
}
