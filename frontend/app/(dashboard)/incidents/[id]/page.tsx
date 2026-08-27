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
  addIncidentNote
} from "@/lib/api/incidents";
import { useWorkspace } from "@/hooks/use-workspace";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { 
  Loader2, ArrowLeft, AlertTriangle, CheckCircle2, 
  Clock, Server, Activity, User, MessageSquare, ListTree, ShieldCheck
} from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/hooks/use-auth";

export default function IncidentDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  
  const incidentId = parseInt(params.id as string, 10);
  const [newNote, setNewNote] = useState("");

  const { projects, jobs, alertRules, projectMap, jobMap, alertRuleMap, canManageProject, isLoading: isLoadingWorkspace } = useWorkspace();

  const { data: incident, isLoading: isLoadingIncident, isError } = useQuery({
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
    },
    onError: (err: any) => alert(err.response?.data?.error || "Failed to acknowledge"),
  });

  const resolveMutation = useMutation({
    mutationFn: () => resolveIncident(incidentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
    },
    onError: (err: any) => alert(err.response?.data?.error || "Failed to resolve"),
  });

  const noteMutation = useMutation({
    mutationFn: (content: string) => addIncidentNote(incidentId, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-notes", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
      setNewNote("");
    },
  });

  const reopenMutation = useMutation({
    mutationFn: () => import("@/lib/api/incidents").then(m => m.reopenIncident(incidentId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
    },
    onError: (err: any) => alert(err.response?.data?.error || err.response?.data?.detail || "Failed to reopen"),
  });

  const project = incident ? projects.find(p => p.id === incident.project) : null;
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
    queryFn: () => import("@/lib/api/teams").then(m => m.getTeamMembers(project!.team)),
    enabled: !!project?.team && hasManagePermission,
  });

  const assignMutation = useMutation({
    mutationFn: (memberId: number) => import("@/lib/api/incidents").then(m => m.assignIncident(incidentId, memberId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incident-events", incidentId] });
    },
    onError: (err: any) => alert(err.response?.data?.error || err.response?.data?.detail || "Failed to assign"),
  });

  if (isLoading) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  if (isError || !incident) return <div className="p-8 text-destructive">Failed to load incident.</div>;

  const job = incident.job ? jobs.find(j => j.id === incident.job) : null;
  const alertRule = incident.alert_rule ? alertRules.find(r => r.id === incident.alert_rule) : null;
  const tm = incident.trigger_metadata || {};

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "OPEN": return <Badge variant="destructive" className="px-3 py-1 text-sm shadow-sm">Open</Badge>;
      case "ACKNOWLEDGED": return <Badge variant="secondary" className="bg-amber-500/10 text-amber-600 border-amber-500/20 px-3 py-1 text-sm">Acknowledged</Badge>;
      case "RESOLVED": return <Badge variant="outline" className="border-green-500/50 text-green-600 bg-green-500/10 px-3 py-1 text-sm">Resolved</Badge>;
      default: return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6 max-w-5xl">
      <Button variant="ghost" size="sm" onClick={() => router.push("/incidents")} className="text-muted-foreground -ml-3 mb-2">
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
            <Badge variant="outline" className={incident.severity === "CRITICAL" ? "text-destructive border-destructive" : ""}>
              {incident.severity}
            </Badge>
          </div>
          
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
            {project ? (
              <Link href={`/projects?project_id=${project.id}`} className="flex items-center gap-1.5 hover:text-foreground transition-colors">
                <Server className="h-4 w-4" /> {project.name}
              </Link>
            ) : (
              <span className="flex items-center gap-1.5"><Server className="h-4 w-4" /> Unknown Project</span>
            )}
            
            {job ? (
              <Link href={`/jobs?job_id=${job.id}`} className="flex items-center gap-1.5 hover:text-foreground transition-colors">
                <Activity className="h-4 w-4" /> {job.name}
              </Link>
            ) : (
              <span className="flex items-center gap-1.5"><Activity className="h-4 w-4" /> Project-level</span>
            )}
            <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" /> {new Date(incident.created_at).toLocaleString()}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {canAckOrResolve && incident.status === "OPEN" && (
            <Button onClick={() => ackMutation.mutate()} disabled={ackMutation.isPending} variant="secondary">
              Acknowledge
            </Button>
          )}
          {canAckOrResolve && incident.status !== "RESOLVED" && (
            <Button onClick={() => resolveMutation.mutate()} disabled={resolveMutation.isPending} variant="default">
              <CheckCircle2 className="mr-2 h-4 w-4" /> Resolve
            </Button>
          )}
          {hasManagePermission && incident.status === "RESOLVED" && (
            <Button onClick={() => { if(window.confirm("Are you sure you want to reopen this incident?")) reopenMutation.mutate(); }} disabled={reopenMutation.isPending} variant="outline">
              Reopen Incident
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: Details & Trigger */}
        <div className="md:col-span-1 space-y-6">
          <div className="rounded-xl border bg-card p-5 shadow-sm">
            <h3 className="font-semibold mb-4 flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-primary" /> Trigger Details</h3>
            <div className="space-y-4">
              <div>
                <p className="text-xs text-muted-foreground font-medium uppercase mb-1">Metric</p>
                <p className="text-sm font-medium">{tm.metric_type ? tm.metric_type.replace("_", " ") : "Unknown"}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase mb-1">Actual Value</p>
                  <p className="text-xl font-mono text-destructive">{tm.metric_value !== undefined ? tm.metric_value : (tm.actual_value !== undefined ? tm.actual_value : "-")}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase mb-1">Threshold</p>
                  <p className="text-xl font-mono">{tm.threshold !== undefined ? tm.threshold : "-"}</p>
                </div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground font-medium uppercase mb-1">Alert Rule</p>
                {alertRule ? (
                  <Link href="/alerts" className="text-sm font-medium text-primary hover:underline flex items-center gap-1.5 bg-primary/5 w-fit px-2 py-1 rounded-md border border-primary/20">
                    <Activity className="h-3.5 w-3.5" />
                    {alertRule.metric.replace(/_/g, " ")} {alertRule.metric.includes("ANOMALY") ? "(Anomaly)" : `> ${alertRule.threshold}`}
                  </Link>
                ) : (
                  <p className="text-sm font-mono bg-muted px-2 py-1 rounded inline-block">{incident.alert_rule || "-"}</p>
                )}
              </div>
            </div>
          </div>

          {/* Reliability Finding Context Card if applicable */}
          {(tm.reliability_finding_id || [
            "MISSED_EXECUTION",
            "STALLED_EXECUTION",
            "OVERDUE_EXECUTION",
            "FAILURE_RATE_ANOMALY",
            "RETRY_RATE_ANOMALY",
            "DURATION_ANOMALY",
            "EXECUTION_VOLUME_ANOMALY",
          ].includes(tm.metric_type || alertRule?.metric || "") || (alertRule?.metric && alertRule.metric.includes("ANOMALY"))) && (
            <div className="rounded-xl border border-primary/20 bg-primary/5 p-5 shadow-sm space-y-3">
              <h3 className="font-semibold flex items-center gap-2 text-primary">
                <ShieldCheck className="h-4 w-4" /> Reliability Finding
              </h3>
              <div className="space-y-2 text-xs">
                <div>
                  <p className="text-muted-foreground uppercase font-medium text-[10px]">Condition</p>
                  <p className="font-semibold text-foreground text-sm mt-0.5">
                    {(tm.condition_type || tm.metric_type || alertRule?.metric || "Reliability Violation").replace(/_/g, " ")}
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
          {hasManagePermission && (
            <div className="rounded-xl border bg-card p-5 shadow-sm">
              <h3 className="font-semibold mb-4 flex items-center gap-2"><User className="h-4 w-4 text-primary" /> Assignment</h3>
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">Assign this incident to a team member to investigate.</p>
                {incident.assigned_to_name && (
                  <div className="flex items-center gap-2 p-2.5 bg-muted/30 border rounded-md">
                    <User className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">
                      Assigned to: {isAssignee ? "You" : incident.assigned_to_name}
                    </span>
                  </div>
                )}
                <div className="flex gap-2">
                  <select 
                    className="flex h-9 w-full items-center justify-between whitespace-nowrap rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    value={incident.assigned_to || ""}
                    onChange={(e) => assignMutation.mutate(Number(e.target.value))}
                    disabled={assignMutation.isPending}
                  >
                    <option value="">Unassigned</option>
                    {teamMembers.map((member: any) => (
                      <option key={member.id} value={member.id}>
                        {member.user.first_name} {member.user.last_name} ({member.user.email})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Timeline & Notes */}
        <div className="md:col-span-2">
          <Tabs defaultValue="timeline" className="w-full">
            <TabsList className="grid w-full grid-cols-2 mb-4">
              <TabsTrigger value="timeline" className="flex items-center gap-2">
                <ListTree className="h-4 w-4" /> Timeline
              </TabsTrigger>
              <TabsTrigger value="notes" className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4" /> Investigation Notes ({notes.length})
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="timeline" className="rounded-xl border bg-card p-6 shadow-sm min-h-[400px]">
              <h3 className="font-semibold mb-6">Activity Timeline</h3>
              <div className="space-y-6">
                {events.map((event, i) => (
                  <div key={event.id} className="flex gap-4 relative">
                    {i < events.length - 1 && <div className="absolute left-[11px] top-7 bottom-[-16px] w-px bg-border" />}
                    
                    <div className="h-6 w-6 rounded-full border-2 bg-background flex items-center justify-center shrink-0 mt-0.5 z-10">
                      <div className={`h-2 w-2 rounded-full ${
                        event.event_type.includes("RESOLVED") ? "bg-green-500" :
                        event.event_type === "CREATED" ? "bg-destructive" : "bg-primary"
                      }`} />
                    </div>
                    
                    <div className="flex-1 pb-2">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium capitalize">{event.event_type.replace("_", " ").toLowerCase()}</p>
                        <span className="text-xs text-muted-foreground">{new Date(event.event_time).toLocaleString()}</span>
                      </div>
                      {event.actor_name && event.event_type !== "ASSIGNED" && (
                        <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                          <User className="h-3 w-3" /> by {event.actor_name}
                        </p>
                      )}
                      {event.event_type === "ASSIGNED" && (
                        <p className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded">
                          Assigned to: <span className="font-medium text-foreground">{event.metadata?.new_assignee_name || "Team Member"}</span>
                          {event.actor_name && <span className="text-xs text-muted-foreground ml-2">(by {event.actor_name})</span>}
                        </p>
                      )}
                      {event.event_type === "ACKNOWLEDGED" && (event.metadata?.acknowledged_by_name || event.actor_name) && (
                        <p className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded">
                          Acknowledged by: <span className="font-medium text-foreground">{event.metadata?.acknowledged_by_name || event.actor_name}</span>
                        </p>
                      )}
                      {event.event_type === "MANUALLY_RESOLVED" && (event.metadata?.resolved_by_name || event.actor_name) && (
                        <p className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded">
                          Resolved by: <span className="font-medium text-foreground">{event.metadata?.resolved_by_name || event.actor_name}</span>
                        </p>
                      )}
                      {event.event_type === "AUTO_RESOLVED" && (
                        <p className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded">
                          Resolved by: <span className="font-medium text-foreground">System (Auto-recovery)</span>
                        </p>
                      )}
                      {event.event_type === "REOPENED" && (event.metadata?.reopened_by_name || event.actor_name) && (
                        <p className="text-sm text-muted-foreground mt-2 bg-muted/50 p-2 rounded">
                          Reopened by: <span className="font-medium text-foreground">{event.metadata?.reopened_by_name || event.actor_name}</span>
                        </p>
                      )}
                      {event.metadata?.reason && (
                        <p className="text-sm text-muted-foreground mt-2 italic bg-muted/50 p-2 rounded">{event.metadata.reason}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="notes" className="rounded-xl border bg-card p-6 shadow-sm min-h-[400px] flex flex-col">
              <h3 className="font-semibold mb-6">Investigation Notes</h3>
              
              <div className="flex-1 space-y-4 mb-6">
                {notes.length === 0 ? (
                  <div className="h-32 flex items-center justify-center text-muted-foreground text-sm italic bg-muted/20 rounded-lg border border-dashed">
                    No notes added yet.
                  </div>
                ) : (
                  notes.map(note => (
                    <div key={note.id} className="bg-muted/30 border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium flex items-center gap-1.5"><User className="h-3.5 w-3.5 text-muted-foreground"/> {note.author_name}</span>
                        <span className="text-xs text-muted-foreground">{new Date(note.created_at).toLocaleString()}</span>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{note.content}</p>
                    </div>
                  ))
                )}
              </div>

              <div className="mt-auto pt-4 border-t">
                <Textarea 
                  placeholder="Add a note about your investigation..." 
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  className="mb-3 resize-none"
                  rows={3}
                />
                <div className="flex items-center justify-between mt-3">
                  <span className="text-xs text-muted-foreground flex items-center gap-1.5 bg-muted/50 px-2 py-1 rounded">
                    <AlertTriangle className="h-3.5 w-3.5" /> 
                    Notes are immutable once saved
                  </span>
                  <Button 
                    onClick={() => noteMutation.mutate(newNote)}
                    disabled={!newNote.trim() || noteMutation.isPending}
                    className="w-full sm:w-auto"
                  >
                    {noteMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin"/> : null}
                    Post Note
                  </Button>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
