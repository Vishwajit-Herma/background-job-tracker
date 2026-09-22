"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getIncidents } from "@/lib/api/incidents";
import { getProjects, Project } from "@/lib/api/projects";
import { getJobs, Job } from "@/lib/api/jobs";
import { getAlertRules, AlertRule } from "@/lib/api/alerts";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Loader2, AlertTriangle, ChevronRight, Activity, CalendarClock } from "lucide-react";
import { PaginationControls } from "@/components/bjt/pagination";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, User } from "lucide-react";
import { useDebounce } from "@/hooks/use-debounce";
import { useAuth } from "@/hooks/use-auth";
import { getTriggerSummary } from "@/lib/incident-trigger-utils";
import { useProject } from "@/components/bjt/project-provider";
import { ProjectSelectFilter } from "@/components/bjt/project-select-filter";

function IncidentsPageContent() {
  const [page, setPage] = useState(1);
  const searchParams = useSearchParams();
  const projectParam = searchParams.get("project");

  const { data: projects = [] } = useQuery<Project[]>({ queryKey: ["projects"], queryFn: () => getProjects() });
  const { data: jobs = [] } = useQuery({ queryKey: ["jobs"], queryFn: () => getJobs() });
  const { data: alertRules = [] } = useQuery<AlertRule[]>({ queryKey: ["alertRules"], queryFn: () => getAlertRules() });

  const projectMap = new Map<number, Project>(projects.map(p => [p.id, p]));
  const jobMap = new Map<number, Job>(jobs.map(j => [j.id, j]));
  const alertRuleMap = new Map<number, AlertRule>(alertRules.map(r => [r.id, r]));

  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [assigneeFilter, setAssigneeFilter] = useState("all");
  const debouncedSearch = useDebounce(search, 500);
  const { user } = useAuth();
  const { selectedProjectId } = useProject();

  const effectiveProjectId =
    projectParam !== null && projectParam !== undefined
      ? projectParam === "all"
        ? "all"
        : parseInt(projectParam, 10) || "all"
      : selectedProjectId;

  const { data: paginatedIncidents, isLoading, isError } = useQuery({
    queryKey: ["incidents", page, debouncedSearch, ordering, statusFilter, severityFilter, assigneeFilter, effectiveProjectId],
    queryFn: () => getIncidents({ 
      page, 
      search: debouncedSearch, 
      ordering, 
      status: statusFilter !== "all" ? statusFilter : undefined,
      severity: severityFilter !== "all" ? severityFilter : undefined,
      assigned_to__user: assigneeFilter === "me" ? user?.id || (user as any)?.pk : undefined,
      project: effectiveProjectId !== "all" && !isNaN(effectiveProjectId as number) ? (effectiveProjectId as number) : undefined,
    }),
  });

  const incidents = paginatedIncidents?.data || [];
  const totalPages = paginatedIncidents?.totalPages || 1;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "OPEN": return <Badge variant="destructive">Open</Badge>;
      case "ACKNOWLEDGED": return <Badge variant="secondary" className="bg-amber-500/10 text-amber-600 border-amber-500/20">Acknowledged</Badge>;
      case "RESOLVED": return <Badge variant="outline" className="border-green-500/50 text-green-600 bg-green-500/10">Resolved</Badge>;
      default: return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Incidents</h2>
          <p className="text-muted-foreground mt-1">
            Track and investigate reliability issues triggered by your alert rules.
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-card p-3 rounded-md border">
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search incidents by ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="flex w-full sm:w-auto gap-3 flex-wrap sm:flex-nowrap">
          <ProjectSelectFilter className="w-full sm:w-44" />
          <div className="w-full sm:w-40">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Status">
                  {statusFilter === "all" && "All Statuses"}
                  {statusFilter === "OPEN" && "Open"}
                  {statusFilter === "ACKNOWLEDGED" && "Acknowledged"}
                  {statusFilter === "RESOLVED" && "Resolved"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="OPEN">Open</SelectItem>
                <SelectItem value="ACKNOWLEDGED">Acknowledged</SelectItem>
                <SelectItem value="RESOLVED">Resolved</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-36">
            <Select value={severityFilter} onValueChange={setSeverityFilter}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Severity">
                  {severityFilter === "all" && "All Severities"}
                  {severityFilter === "CRITICAL" && "Critical"}
                  {severityFilter === "DEGRADED" && "Degraded"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severities</SelectItem>
                <SelectItem value="CRITICAL">Critical</SelectItem>
                <SelectItem value="DEGRADED">Degraded</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-36">
            <Select value={assigneeFilter} onValueChange={setAssigneeFilter}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Assignee">
                  {assigneeFilter === "all" && "All Assignees"}
                  {assigneeFilter === "me" && "Assigned to me"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Assignees</SelectItem>
                <SelectItem value="me">Assigned to me</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-48">
            <Select value={ordering} onValueChange={setOrdering}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Sort by">
                  {ordering === "-created_at" && "Newest First"}
                  {ordering === "created_at" && "Oldest First"}
                  {ordering === "-updated_at" && "Recently Updated"}
                  {ordering === "severity" && "Severity (High to Low)"}
                  {ordering === "-severity" && "Severity (Low to High)"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="-created_at">Newest First</SelectItem>
                <SelectItem value="created_at">Oldest First</SelectItem>
                <SelectItem value="-updated_at">Recently Updated</SelectItem>
                <SelectItem value="severity">Severity (High to Low)</SelectItem>
                <SelectItem value="-severity">Severity (Low to High)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <div className="rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Incident</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Assignee</TableHead>
              <TableHead>Context (Project / Job)</TableHead>
              <TableHead>Trigger Reason</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="h-24 text-center text-muted-foreground">
                  <div className="flex justify-center items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading incidents...
                  </div>
                </TableCell>
              </TableRow>
            ) : isError ? (
              <TableRow>
                <TableCell colSpan={8} className="h-24 text-center text-destructive">
                  Failed to load incidents.
                </TableCell>
              </TableRow>
            ) : incidents.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="h-32 text-center">
                  <div className="flex flex-col items-center text-muted-foreground">
                    <AlertTriangle className="h-8 w-8 mb-2 opacity-20" />
                    <p>No incidents found.</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              incidents.map((incident) => {
                const project = projectMap.get(incident.project);
                const job = incident.job ? jobMap.get(incident.job) : null;
                const tm = incident.trigger_metadata || {};

                return (
                  <TableRow key={incident.id} className="cursor-pointer hover:bg-muted/50 transition-colors">
                    <TableCell>
                      <Link href={`/incidents/${incident.id}`} className="block font-medium">
                        INC-{incident.id}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Link href={`/incidents/${incident.id}`} className="block">
                        {getStatusBadge(incident.status)}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Link href={`/incidents/${incident.id}`} className="block">
                        <Badge variant="outline" className={incident.severity === "CRITICAL" ? "text-destructive border-destructive/30 bg-destructive/5" : ""}>
                          {incident.severity}
                        </Badge>
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Link href={`/incidents/${incident.id}`} className="block">
                        {incident.assigned_to_name || incident.assigned_to ? (
                          <div className="flex items-center gap-1.5 text-sm font-medium">
                            <User className="h-3.5 w-3.5 text-muted-foreground" />
                            {incident.assigned_to_name || `Member #${incident.assigned_to}`}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground italic">Unassigned</span>
                        )}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Link href={`/incidents/${incident.id}`} className="block">
                        <div className="flex flex-col">
                          <span className="font-medium text-sm">
                            {job ? job.name : "Project-level"}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {project?.name || `Project #${incident.project}`}
                          </span>
                        </div>
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Link href={`/incidents/${incident.id}`} className="block max-w-[240px]">
                        {(() => {
                          const rule = incident.alert_rule ? alertRuleMap.get(incident.alert_rule) : null;
                          const summary = getTriggerSummary(tm, rule);

                          return (
                            <div className="text-xs flex flex-col gap-0.5">
                              <span className="font-semibold text-foreground truncate">{summary.title}</span>
                              <span className="text-muted-foreground text-[11px] truncate">
                                {summary.primaryValue}
                                {summary.secondaryValue ? ` (${summary.secondaryValue})` : ""}
                              </span>
                            </div>
                          );
                        })()}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Link href={`/incidents/${incident.id}`} className="block text-sm text-muted-foreground">
                        {new Date(incident.created_at).toLocaleString()}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Link href={`/incidents/${incident.id}`} className="flex justify-end pr-4 text-muted-foreground hover:text-foreground">
                        <ChevronRight className="h-4 w-4" />
                      </Link>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>

        {totalPages > 1 && (
          <div className="px-4 py-3 border-t bg-muted/10">
            <PaginationControls page={page} totalPages={totalPages} setPage={setPage} />
          </div>
        )}
      </div>
    </div>
  );
}

export default function IncidentsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">Loading incidents...</div>}>
      <IncidentsPageContent />
    </Suspense>
  );
}

