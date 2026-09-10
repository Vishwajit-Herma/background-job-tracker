"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getIncident,
  getIncidentEvents,
  getIncidentNotes,
  acknowledgeIncident,
  resolveIncident,
  reopenIncident,
  addIncidentNote,
  IncidentEvent,
} from "@/lib/api/incidents";
import { useWorkspace } from "@/hooks/use-workspace";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Loader2,
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Server,
  Activity,
  User,
  MessageSquare,
  ListTree,
  ShieldCheck,
  BookOpen,
  FileText,
  Brain,
  Sparkles,
  Play,
  XCircle,
  SkipForward,
} from "lucide-react";
import Link from "next/link";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toastError, toastSuccess } from "@/lib/toast";
import { useAuth } from "@/hooks/use-auth";
import { IncidentIntelligenceSection } from "@/components/bjt/incidents/incident-intelligence-section";
import { RecommendedRunbooks } from "@/components/bjt/incidents/runbook/recommended-runbooks";
import { PostmortemSection } from "@/components/bjt/incidents/postmortem/postmortem-section";
import { AskAIPanel } from "@/components/bjt/incidents/ai/ask-ai-panel";

// ─── Timeline Event Rendering ─────────────────────────────────────────────────

function getEventDotColor(eventType: IncidentEvent["event_type"]): string {
  if (eventType === "CREATED") return "bg-destructive";
  if (eventType.includes("RESOLVED")) return "bg-emerald-500";
  if (eventType === "RUNBOOK_COMPLETED") return "bg-emerald-500";
  if (eventType === "RUNBOOK_CANCELLED") return "bg-amber-500";
  if (eventType === "RUNBOOK_STARTED") return "bg-blue-500";
  if (eventType === "POSTMORTEM_COMPLETED") return "bg-violet-500";
  if (eventType === "POSTMORTEM_SUBMITTED") return "bg-violet-400";
  return "bg-primary";
}

function getEventIcon(eventType: IncidentEvent["event_type"]) {
  if (eventType === "RUNBOOK_STARTED") return <Play className="h-3 w-3" />;
  if (eventType === "RUNBOOK_COMPLETED") return <CheckCircle2 className="h-3 w-3" />;
  if (eventType === "RUNBOOK_CANCELLED") return <XCircle className="h-3 w-3" />;
  if (eventType === "POSTMORTEM_SUBMITTED") return <FileText className="h-3 w-3" />;
  if (eventType === "POSTMORTEM_COMPLETED") return <CheckCircle2 className="h-3 w-3" />;
  return null;
}

function formatEventLabel(eventType: string): string {
  return eventType.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function TimelineEvent({ event, isLast }: { event: IncidentEvent; isLast: boolean }) {
  const dotColor = getEventDotColor(event.event_type);

  return (
    <div className="flex gap-4 relative">
      {!isLast && <div className="absolute left-[11px] top-7 bottom-[-16px] w-px bg-border" />}
      <div className="h-6 w-6 rounded-full border-2 bg-background flex items-center justify-center shrink-0 mt-0.5 z-10">
        <div className={`h-2 w-2 rounded-full ${dotColor}`} />
      </div>
      <div className="flex-1 pb-2">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium">{formatEventLabel(event.event_type)}</p>
          <span className="text-xs text-muted-foreground">{new Date(event.event_time).toLocaleString()}</span>
        </div>
        {event.actor_name && event.event_type !== "ASSIGNED" && (
          <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
            <User className="h-3 w-3" /> by {event.actor_name}
          </p>
        )}
        {event.event_type === "ASSIGNED" && (
          <p className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded">
            Assigned to:{" "}
            <span className="font-medium text-foreground">
              {event.metadata?.new_assignee_name || "Team Member"}
            </span>
            {event.actor_name && (
              <span className="text-xs text-muted-foreground ml-2">(by {event.actor_name})</span>
            )}
          </p>
        )}
        {event.event_type === "ACKNOWLEDGED" &&
          (event.metadata?.acknowledged_by_name || event.actor_name) && (
            <p className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded">
              Acknowledged by:{" "}
              <span className="font-medium text-foreground">
                {event.metadata?.acknowledged_by_name || event.actor_name}
              </span>
            </p>
          )}
        {(event.event_type === "MANUALLY_RESOLVED" || event.event_type === "AUTO_RESOLVED") && (
          <p className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded">
            Resolved by:{" "}
            <span className="font-medium text-foreground">
              {event.event_type === "AUTO_RESOLVED"
                ? "System (Auto-recovery)"
                : event.metadata?.resolved_by_name || event.actor_name || "Unknown"}
            </span>
          </p>
        )}
        {event.event_type === "REOPENED" &&
          (event.metadata?.reopened_by_name || event.actor_name) && (
            <p className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded">
              Reopened by:{" "}
              <span className="font-medium text-foreground">
                {event.metadata?.reopened_by_name || event.actor_name}
              </span>
            </p>
          )}
        {event.event_type === "RUNBOOK_STARTED" && event.metadata?.runbook_name && (
          <p className="text-sm text-muted-foreground mt-2 bg-blue-500/5 border border-blue-500/20 p-2 rounded flex items-center gap-1.5">
            <BookOpen className="h-3.5 w-3.5 text-blue-500" />
            Runbook: <span className="font-medium text-foreground">{event.metadata.runbook_name}</span>
          </p>
        )}
        {(event.event_type === "RUNBOOK_COMPLETED" || event.event_type === "RUNBOOK_CANCELLED") &&
          event.metadata?.runbook_name && (
            <p className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded flex items-center gap-1.5">
              <BookOpen className="h-3.5 w-3.5" />
              Runbook: <span className="font-medium text-foreground">{event.metadata.runbook_name}</span>
              {" "}·{" "}
              <span className={event.event_type === "RUNBOOK_COMPLETED" ? "text-emerald-600" : "text-amber-600"}>
                {event.event_type === "RUNBOOK_COMPLETED" ? "Completed" : "Cancelled"}
              </span>
            </p>
          )}
        {(event.event_type === "POSTMORTEM_SUBMITTED" ||
          event.event_type === "POSTMORTEM_COMPLETED") && (
          <p className="text-sm text-muted-foreground mt-2 bg-violet-500/5 border border-violet-500/20 p-2 rounded flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 text-violet-500" />
            Postmortem{" "}
            {event.event_type === "POSTMORTEM_SUBMITTED" ? "submitted for review" : "completed"}
          </p>
        )}
        {event.metadata?.reason && (
          <p className="text-sm text-muted-foreground mt-2 italic bg-muted/50 p-2 rounded">
            {event.metadata.reason}
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function IncidentDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const incidentId = parseInt(params.id as string, 10);
  const [newNote, setNewNote] = useState("");
  const [showReopenDialog, setShowReopenDialog] = useState(false);
  const [isAiOpen, setIsAiOpen] = useState(false);

  const {
    projects,
    jobs,
    alertRules,
    canManageProject,
    isLoading: isLoadingWorkspace,
  } = useWorkspace();

  const {
    data: incident,
    isLoading: isLoadingIncident,
    isError,
  } = useQuery({
    queryKey: ["incident", incidentId],
    queryFn: () => getIncident(incidentId),
    enabled: !!incidentId,
  });

  const isLoading = isLoadingIncident || isLoadingWorkspace;

  const { data: events = [] } = useQuery({
    queryKey: ["incident-events", incidentId],
    queryFn: () => getIncidentEvents(incidentId),
    enabled: !!incidentId,
  });

  const { data: notes = [] } = useQuery({
    queryKey: ["incident-notes", incidentId],
    queryFn: () => getIncidentNotes(incidentId),
    enabled: !!incidentId,
  });

  const ackMutation = useMutation({
    mutationFn: () => acknowledgeIncident(incidentId),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["incident", incidentId] });
      await queryClient.cancelQueries({ queryKey: ["incidents"] });

      const previousIncident = queryClient.getQueryData(["incident", incidentId]);

      queryClient.setQueryData(["incident", incidentId], (old: any) =>
        old ? { ...old, status: "ACKNOWLEDGED" } : old
      );

      queryClient.setQueriesData({ queryKey: ["incidents"] }, (old: any) => {
        if (!old) return old;
        if (Array.isArray(old)) {
          return old.map((inc: any) => (inc.id === incidentId ? { ...inc, status: "ACKNOWLEDGED" } : inc));
        }
        if (old.data && Array.isArray(old.data)) {
          return {
            ...old,
            data: old.data.map((inc: any) => (inc.id === incidentId ? { ...inc, status: "ACKNOWLEDGED" } : inc)),
          };
        }
        return old;
      });

      return { previousIncident };
    },
    onError: (err: any, _vars, context) => {
      if (context?.previousIncident) {
        queryClient.setQueryData(["incident", incidentId], context.previousIncident);
      }
      toastError("Failed to Acknowledge", err);
    },
    onSuccess: (updatedIncident: any) => {
      toastSuccess("Incident Acknowledged");
      if (updatedIncident) {
        queryClient.setQueryData(["incident", incidentId], updatedIncident);
        queryClient.setQueriesData({ queryKey: ["incidents"] }, (old: any) => {
          if (!old) return old;
          if (Array.isArray(old)) {
            return old.map((inc: any) => (inc.id === incidentId ? updatedIncident : inc));
          }
          if (old.data && Array.isArray(old.data)) {
            return {
              ...old,
              data: old.data.map((inc: any) => (inc.id === incidentId ? updatedIncident : inc)),
            };
          }
          return old;
        });
      }
      // Append event locally to avoid GET /api/incidents/:id/events/ refetch
      const ackEvent: IncidentEvent = {
        id: Date.now(),
        event_type: "ACKNOWLEDGED",
        actor: (user as any)?.pk || user?.id || null,
        actor_name: (user as any)?.first_name ? `${(user as any).first_name} ${(user as any).last_name || ""}`.trim() : user?.email || "System",
        event_time: new Date().toISOString(),
        metadata: { acknowledged_by_name: user?.email },
      };
      queryClient.setQueryData(["incident-events", incidentId], (old: any) =>
        Array.isArray(old) ? [...old, ackEvent] : [ackEvent]
      );
    },
  });

  const resolveMutation = useMutation({
    mutationFn: () => resolveIncident(incidentId),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["incident", incidentId] });
      await queryClient.cancelQueries({ queryKey: ["incidents"] });

      const previousIncident = queryClient.getQueryData(["incident", incidentId]);

      queryClient.setQueryData(["incident", incidentId], (old: any) =>
        old ? { ...old, status: "RESOLVED", resolution_type: "MANUAL" } : old
      );

      queryClient.setQueriesData({ queryKey: ["incidents"] }, (old: any) => {
        if (!old) return old;
        if (Array.isArray(old)) {
          return old.map((inc: any) => (inc.id === incidentId ? { ...inc, status: "RESOLVED", resolution_type: "MANUAL" } : inc));
        }
        if (old.data && Array.isArray(old.data)) {
          return {
            ...old,
            data: old.data.map((inc: any) => (inc.id === incidentId ? { ...inc, status: "RESOLVED", resolution_type: "MANUAL" } : inc)),
          };
        }
        return old;
      });

      return { previousIncident };
    },
    onError: (err: any, _vars, context) => {
      if (context?.previousIncident) {
        queryClient.setQueryData(["incident", incidentId], context.previousIncident);
      }
      toastError("Failed to Resolve", err);
    },
    onSuccess: (updatedIncident: any) => {
      toastSuccess("Incident Resolved");
      if (updatedIncident) {
        queryClient.setQueryData(["incident", incidentId], updatedIncident);
        queryClient.setQueriesData({ queryKey: ["incidents"] }, (old: any) => {
          if (!old) return old;
          if (Array.isArray(old)) {
            return old.map((inc: any) => (inc.id === incidentId ? updatedIncident : inc));
          }
          if (old.data && Array.isArray(old.data)) {
            return {
              ...old,
              data: old.data.map((inc: any) => (inc.id === incidentId ? updatedIncident : inc)),
            };
          }
          return old;
        });
      }
      // Append event locally to avoid GET /api/incidents/:id/events/ refetch
      const resolveEvent: IncidentEvent = {
        id: Date.now(),
        event_type: "MANUALLY_RESOLVED",
        actor: (user as any)?.pk || user?.id || null,
        actor_name: (user as any)?.first_name ? `${(user as any).first_name} ${(user as any).last_name || ""}`.trim() : user?.email || "System",
        event_time: new Date().toISOString(),
        metadata: { resolved_by_name: user?.email, resolution_type: "MANUAL" },
      };
      queryClient.setQueryData(["incident-events", incidentId], (old: any) =>
        Array.isArray(old) ? [...old, resolveEvent] : [resolveEvent]
      );
    },
  });

  const noteMutation = useMutation({
    mutationFn: (content: string) => addIncidentNote(incidentId, content),
    onSuccess: (newNote: any) => {
      toastSuccess("Note Added");
      if (newNote) {
        queryClient.setQueryData(["incident-notes", incidentId], (old: any) =>
          Array.isArray(old) ? [...old, newNote] : [newNote]
        );
      } else {
        queryClient.invalidateQueries({ queryKey: ["incident-notes", incidentId] });
      }
      setNewNote("");
    },
    onError: (err: any) => toastError("Failed to Add Note", err),
  });

  const reopenMutation = useMutation({
    mutationFn: () => reopenIncident(incidentId),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["incident", incidentId] });
      await queryClient.cancelQueries({ queryKey: ["incidents"] });

      const previousIncident = queryClient.getQueryData(["incident", incidentId]);

      queryClient.setQueryData(["incident", incidentId], (old: any) =>
        old ? { ...old, status: "OPEN" } : old
      );

      queryClient.setQueriesData({ queryKey: ["incidents"] }, (old: any) => {
        if (!old) return old;
        if (Array.isArray(old)) {
          return old.map((inc: any) => (inc.id === incidentId ? { ...inc, status: "OPEN" } : inc));
        }
        if (old.data && Array.isArray(old.data)) {
          return {
            ...old,
            data: old.data.map((inc: any) => (inc.id === incidentId ? { ...inc, status: "OPEN" } : inc)),
          };
        }
        return old;
      });

      return { previousIncident };
    },
    onError: (err: any, _vars, context) => {
      if (context?.previousIncident) {
        queryClient.setQueryData(["incident", incidentId], context.previousIncident);
      }
      toastError("Failed to Reopen", err);
    },
    onSuccess: (updatedIncident: any) => {
      toastSuccess("Incident Reopened");
      if (updatedIncident) {
        queryClient.setQueryData(["incident", incidentId], updatedIncident);
        queryClient.setQueriesData({ queryKey: ["incidents"] }, (old: any) => {
          if (!old) return old;
          if (Array.isArray(old)) {
            return old.map((inc: any) => (inc.id === incidentId ? updatedIncident : inc));
          }
          if (old.data && Array.isArray(old.data)) {
            return {
              ...old,
              data: old.data.map((inc: any) => (inc.id === incidentId ? updatedIncident : inc)),
            };
          }
          return old;
        });
      }
      // Append event locally to avoid GET /api/incidents/:id/events/ refetch
      const reopenEvent: IncidentEvent = {
        id: Date.now(),
        event_type: "REOPENED",
        actor: (user as any)?.pk || user?.id || null,
        actor_name: (user as any)?.first_name ? `${(user as any).first_name} ${(user as any).last_name || ""}`.trim() : user?.email || "System",
        event_time: new Date().toISOString(),
        metadata: { reopened_by_name: user?.email },
      };
      queryClient.setQueryData(["incident-events", incidentId], (old: any) =>
        Array.isArray(old) ? [...old, reopenEvent] : [reopenEvent]
      );
    },
  });

  const project = incident ? projects.find((p) => p.id === incident.project) : null;
  const hasManagePermission = project ? canManageProject(project.id) : false;

  const currentUserId = user?.id || (user as any)?.pk;
  const isAssignee = Boolean(
    incident?.assigned_to_user_id &&
      currentUserId &&
      Number(incident.assigned_to_user_id) === Number(currentUserId)
  );
  const canAckOrResolve = hasManagePermission || isAssignee;

  const { data: teamMembers = [] } = useQuery({
    queryKey: ["team-members", project?.team],
    queryFn: () => import("@/lib/api/teams").then((m) => m.getTeamMembers(project!.team)),
    enabled: !!project?.team,
  });

  const assignMutation = useMutation({
    mutationFn: (memberId: number | null) =>
      import("@/lib/api/incidents").then((m) => m.assignIncident(incidentId, memberId)),
    onMutate: async (memberId: number | null) => {
      await queryClient.cancelQueries({ queryKey: ["incident", incidentId] });
      await queryClient.cancelQueries({ queryKey: ["incidents"] });

      const previousIncident = queryClient.getQueryData(["incident", incidentId]);
      const member = teamMembers.find((m: any) => m.id === memberId);
      const assigneeName = member
        ? [member.user?.first_name, member.user?.last_name].filter(Boolean).join(" ") ||
          member.user?.email ||
          `Member #${member.id}`
        : null;

      queryClient.setQueryData(["incident", incidentId], (old: any) =>
        old ? { ...old, assigned_to: memberId, assigned_to_name: assigneeName } : old
      );

      queryClient.setQueriesData({ queryKey: ["incidents"] }, (old: any) => {
        if (!old) return old;
        if (Array.isArray(old)) {
          return old.map((inc: any) =>
            inc.id === incidentId ? { ...inc, assigned_to: memberId, assigned_to_name: assigneeName } : inc
          );
        }
        if (old.data && Array.isArray(old.data)) {
          return {
            ...old,
            data: old.data.map((inc: any) =>
              inc.id === incidentId ? { ...inc, assigned_to: memberId, assigned_to_name: assigneeName } : inc
            ),
          };
        }
        return old;
      });

      return { previousIncident };
    },
    onError: (err: any, _vars, context) => {
      if (context?.previousIncident) {
        queryClient.setQueryData(["incident", incidentId], context.previousIncident);
      }
      toastError("Assignment Failed", err);
    },
    onSuccess: (updatedIncident: any) => {
      toastSuccess("Incident Assignee Updated");
      if (updatedIncident) {
        queryClient.setQueryData(["incident", incidentId], updatedIncident);
        queryClient.setQueriesData({ queryKey: ["incidents"] }, (old: any) => {
          if (!old) return old;
          if (Array.isArray(old)) {
            return old.map((inc: any) => (inc.id === incidentId ? updatedIncident : inc));
          }
          if (old.data && Array.isArray(old.data)) {
            return {
              ...old,
              data: old.data.map((inc: any) => (inc.id === incidentId ? updatedIncident : inc)),
            };
          }
          return old;
        });
      }
    },
  });

  if (isLoading)
    return (
      <div className="p-8 flex justify-center">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  if (isError || !incident)
    return <div className="p-8 text-destructive">Failed to load incident.</div>;

  const job = incident.job ? jobs.find((j) => j.id === incident.job) : null;
  const alertRule = incident.alert_rule ? alertRules.find((r) => r.id === incident.alert_rule) : null;
  const tm = incident.trigger_metadata || {};

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "OPEN":
        return (
          <Badge variant="destructive" className="px-3 py-1 text-sm shadow-sm">
            Open
          </Badge>
        );
      case "ACKNOWLEDGED":
        return (
          <Badge variant="secondary" className="bg-amber-500/10 text-amber-600 border-amber-500/20 px-3 py-1 text-sm">
            Acknowledged
          </Badge>
        );
      case "RESOLVED":
        return (
          <Badge variant="outline" className="border-green-500/50 text-green-600 bg-green-500/10 px-3 py-1 text-sm">
            Resolved
          </Badge>
        );
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6 max-w-6xl">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push("/incidents")}
        className="text-muted-foreground -ml-3 mb-2"
      >
        <ArrowLeft className="h-4 w-4 mr-2" /> Back to Incidents
      </Button>

      {/* Header Panel */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 p-6 rounded-xl border bg-card shadow-sm">
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">INC-{incident.id}</h1>
            {getStatusBadge(incident.status)}
            {incident.status === "RESOLVED" && (
              <Badge variant="outline" className="bg-muted/50 text-muted-foreground font-medium text-xs">
                {incident.resolution_type === "AUTOMATIC" ? "Auto-resolved" : "Manually resolved"}
              </Badge>
            )}
            <Badge
              variant="outline"
              className={incident.severity === "CRITICAL" ? "text-destructive border-destructive" : ""}
            >
              {incident.severity}
            </Badge>
          </div>

          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
            {project ? (
              <Link
                href={`/projects?project_id=${project.id}`}
                className="flex items-center gap-1.5 hover:text-foreground transition-colors"
              >
                <Server className="h-4 w-4" /> {project.name}
              </Link>
            ) : (
              <span className="flex items-center gap-1.5">
                <Server className="h-4 w-4" /> Unknown Project
              </span>
            )}

            {job ? (
              <Link
                href={`/jobs?job_id=${job.id}`}
                className="flex items-center gap-1.5 hover:text-foreground transition-colors"
              >
                <Activity className="h-4 w-4" /> {job.name}
              </Link>
            ) : (
              <span className="flex items-center gap-1.5">
                <Activity className="h-4 w-4" /> Project-level
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <Clock className="h-4 w-4" /> {new Date(incident.created_at).toLocaleString()}
            </span>
            <div className="flex items-center gap-1.5">
              <User className="h-4 w-4 text-muted-foreground" />
              {hasManagePermission ? (
                <select
                  className="bg-background border border-input rounded px-2 py-0.5 text-xs focus:outline-none focus:border-primary font-medium cursor-pointer"
                  value={incident.assigned_to ?? ""}
                  onChange={(e) => {
                    const val = e.target.value ? Number(e.target.value) : null;
                    assignMutation.mutate(val);
                  }}
                >
                  <option value="">Unassigned</option>
                  {teamMembers.map((m: any) => {
                    const name =
                      [m.user?.first_name, m.user?.last_name].filter(Boolean).join(" ") ||
                      m.user?.email ||
                      `Member #${m.id}`;
                    return (
                      <option key={m.id} value={m.id}>
                        {name}
                      </option>
                    );
                  })}
                </select>
              ) : (
                <span className="font-medium text-foreground">
                  {incident.assigned_to_name || "Unassigned"}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={() => setIsAiOpen(true)}
            variant="outline"
            className="border-primary/30 bg-primary/5 hover:bg-primary/10 text-primary gap-1.5 shadow-2xs font-medium"
          >
            <Sparkles className="h-4 w-4 text-primary animate-pulse" /> Ask AI
          </Button>

          {canAckOrResolve && incident.status === "OPEN" && (
            <Button
              onClick={() => ackMutation.mutate()}
              disabled={ackMutation.isPending}
              variant="secondary"
            >
              {ackMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Acknowledge
            </Button>
          )}
          {canAckOrResolve && incident.status !== "RESOLVED" && (
            <Button
              onClick={() => resolveMutation.mutate()}
              disabled={resolveMutation.isPending}
              variant="default"
            >
              <CheckCircle2 className="mr-2 h-4 w-4" /> Resolve
            </Button>
          )}
          {hasManagePermission && incident.status === "RESOLVED" && (
            <Button
              onClick={() => setShowReopenDialog(true)}
              disabled={reopenMutation.isPending}
              variant="outline"
            >
              Reopen Incident
            </Button>
          )}
        </div>
      </div>

      {/* Reopen Confirmation Dialog */}
      <Dialog open={showReopenDialog} onOpenChange={setShowReopenDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Reopen Incident INC-{incident.id}?</DialogTitle>
            <DialogDescription>
              Reopening this incident will change its status back to OPEN and log a timeline event.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setShowReopenDialog(false)}>
              Cancel
            </Button>
            <Button
              disabled={reopenMutation.isPending}
              onClick={() => {
                reopenMutation.mutate();
                setShowReopenDialog(false);
              }}
            >
              {reopenMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              Reopen Incident
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 5-Tab Layout */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-5 mb-6">
          <TabsTrigger value="overview" className="flex items-center gap-1.5 text-xs sm:text-sm">
            <AlertTriangle className="h-4 w-4" />
            <span className="hidden sm:inline">Overview</span>
          </TabsTrigger>
          <TabsTrigger value="intelligence" className="flex items-center gap-1.5 text-xs sm:text-sm">
            <Activity className="h-4 w-4" />
            <span className="hidden sm:inline">Intelligence</span>
          </TabsTrigger>
          <TabsTrigger value="response" className="flex items-center gap-1.5 text-xs sm:text-sm">
            <BookOpen className="h-4 w-4" />
            <span className="hidden sm:inline">Response</span>
          </TabsTrigger>
          <TabsTrigger value="timeline" className="flex items-center gap-1.5 text-xs sm:text-sm">
            <ListTree className="h-4 w-4" />
            <span className="hidden sm:inline">Timeline</span>
          </TabsTrigger>
          <TabsTrigger value="postmortem" className="flex items-center gap-1.5 text-xs sm:text-sm">
            <FileText className="h-4 w-4" />
            <span className="hidden sm:inline">Postmortem</span>
          </TabsTrigger>
        </TabsList>

        {/* ── Overview ── */}
        <TabsContent value="overview">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Trigger Details */}
            <div className="rounded-xl border bg-card p-5 shadow-sm">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-primary" /> Trigger Details
              </h3>
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase mb-1">Metric</p>
                  <p className="text-sm font-medium">
                    {(tm.metric_type || tm.condition_type || alertRule?.metric || "Unknown").replace(/_/g, " ")}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground font-medium uppercase mb-1">
                      Actual Value
                    </p>
                    <p className="text-xl font-mono text-destructive">
                      {tm.metric_value !== undefined
                        ? tm.metric_value
                        : tm.actual_value !== undefined
                        ? tm.actual_value
                        : tm.overdue_by_seconds !== undefined
                        ? `${tm.overdue_by_seconds}s`
                        : tm.runtime_seconds !== undefined
                        ? `${tm.runtime_seconds}s`
                        : "–"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground font-medium uppercase mb-1">
                      Threshold
                    </p>
                    <p className="text-xl font-mono">
                      {tm.threshold !== undefined
                        ? tm.threshold
                        : alertRule?.threshold !== undefined
                        ? alertRule.threshold
                        : "–"}
                    </p>
                  </div>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase mb-1">Alert Rule</p>
                  {alertRule ? (
                    <Link
                      href="/alerts"
                      className="text-sm font-medium text-primary hover:underline flex items-center gap-1.5 bg-primary/5 w-fit px-2 py-1 rounded-md border border-primary/20"
                    >
                      <Activity className="h-3.5 w-3.5" />
                      {alertRule.metric.replace(/_/g, " ")}{" "}
                      {alertRule.metric.includes("ANOMALY") ? "(Anomaly)" : `> ${alertRule.threshold}`}
                    </Link>
                  ) : (
                    <p className="text-sm font-mono bg-muted px-2 py-1 rounded inline-block">
                      {incident.alert_rule || "–"}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Reliability Finding */}
            {(tm.reliability_finding_id ||
              [
                "MISSED_EXECUTION",
                "STALLED_EXECUTION",
                "OVERDUE_EXECUTION",
                "FAILURE_RATE_ANOMALY",
                "RETRY_RATE_ANOMALY",
                "DURATION_ANOMALY",
                "EXECUTION_VOLUME_ANOMALY",
              ].includes(tm.metric_type || alertRule?.metric || "") ||
              (alertRule?.metric && alertRule.metric.includes("ANOMALY"))) && (
              <div className="rounded-xl border border-primary/20 bg-primary/5 p-5 shadow-sm space-y-3">
                <h3 className="font-semibold flex items-center gap-2 text-primary">
                  <ShieldCheck className="h-4 w-4" /> Reliability Finding
                </h3>
                <div className="space-y-2 text-xs">
                  <div>
                    <p className="text-muted-foreground uppercase font-medium text-[10px]">Condition</p>
                    <p className="font-semibold text-foreground text-sm mt-0.5">
                      {(
                        tm.condition_type ||
                        tm.metric_type ||
                        alertRule?.metric ||
                        "Reliability Violation"
                      ).replace(/_/g, " ")}
                    </p>
                  </div>
                  {job && (
                    <div>
                      <p className="text-muted-foreground uppercase font-medium text-[10px]">Job</p>
                      <p className="font-semibold text-foreground text-sm mt-0.5">{job.name}</p>
                    </div>
                  )}
                  {incident.job && (
                    <div className="pt-2">
                      <Link href={`/jobs/${incident.job}/reliability`}>
                        <Button size="sm" variant="default" className="w-full h-8 text-xs gap-1.5">
                          <ShieldCheck className="h-3.5 w-3.5" /> View Job Reliability
                        </Button>
                      </Link>
                    </div>
                  )}
                </div>
              </div>
            )}


            {/* Notes (compact in overview) */}
            <div className="rounded-xl border bg-card p-5 shadow-sm md:col-span-2">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-primary" /> Investigation Notes ({notes.length})
              </h3>
              {notes.length > 0 && (
                <div className="space-y-3 mb-4 max-h-48 overflow-y-auto">
                  {notes.map((note) => (
                    <div key={note.id} className="bg-muted/30 border rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium flex items-center gap-1">
                          <User className="h-3 w-3 text-muted-foreground" /> {note.author_name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {new Date(note.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{note.content}</p>
                    </div>
                  ))}
                </div>
              )}
              <div className="space-y-2">
                <Textarea
                  placeholder="Add a note about your investigation…"
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  className="resize-none"
                  rows={2}
                />
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground flex items-center gap-1.5 bg-muted/50 px-2 py-1 rounded">
                    <AlertTriangle className="h-3.5 w-3.5" /> Notes are immutable once saved
                  </span>
                  <Button
                    size="sm"
                    onClick={() => noteMutation.mutate(newNote)}
                    disabled={!newNote.trim() || noteMutation.isPending}
                  >
                    {noteMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Post Note
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* ── Intelligence ── */}
        <TabsContent value="intelligence">
          <div className="rounded-xl border bg-card p-6 shadow-sm">
            <IncidentIntelligenceSection
              incidentId={incident.id}
              jobId={incident.job}
              projectId={incident.project}
            />
          </div>
        </TabsContent>

        {/* ── Response ── */}
        <TabsContent value="response">
          <div className="rounded-xl border bg-card p-6 shadow-sm">
            <RecommendedRunbooks
              incidentId={incident.id}
              projectId={incident.project}
              jobId={incident.job}
              triggerType={incident.trigger_metadata?.metric_type}
            />
          </div>
        </TabsContent>

        {/* ── Timeline ── */}
        <TabsContent value="timeline">
          <div className="rounded-xl border bg-card p-6 shadow-sm min-h-[400px]">
            <h3 className="font-semibold mb-6">Activity Timeline</h3>
            <div className="space-y-6">
              {events.length === 0 ? (
                <div className="flex items-center justify-center h-32 text-muted-foreground text-sm italic border border-dashed rounded-lg">
                  No events recorded yet.
                </div>
              ) : (
                events.map((event, i) => (
                  <TimelineEvent key={event.id} event={event} isLast={i === events.length - 1} />
                ))
              )}
            </div>
          </div>
        </TabsContent>

        {/* ── Postmortem ── */}
        <TabsContent value="postmortem">
          <div className="rounded-xl border bg-card p-6 shadow-sm">
            <PostmortemSection
              incidentId={incident.id}
              teamId={project?.team}
              hasManagePermission={hasManagePermission}
            />

          </div>
        </TabsContent>
      </Tabs>

      {/* AI Reliability Assistant Slide-over Panel */}
      <AskAIPanel
        incidentId={incident.id}
        open={isAiOpen}
        onOpenChange={setIsAiOpen}
      />
    </div>
  );
}
