"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPaginatedAlertRules, deleteAlertRule, updateAlertRule, AlertRule } from "@/lib/api/alerts";
import { getProjects, Project } from "@/lib/api/projects";
import { getJobs, Job } from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { BellRing, Loader2, Plus, MoreHorizontal, Edit, Trash, Activity, Power, PowerOff } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AlertRuleModal } from "@/components/bjt/alerts/alert-rule-modal";
import { PaginationControls } from "@/components/bjt/pagination";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search } from "lucide-react";
import { useDebounce } from "@/hooks/use-debounce";
import { useWorkspace } from "@/hooks/use-workspace";
import { useAuth } from "@/hooks/use-auth";

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [ruleToEdit, setRuleToEdit] = useState<AlertRule | null>(null);
  const [page, setPage] = useState(1);

  const { user } = useAuth();
  const isGlobalStaff = Boolean(user?.is_staff);
  const { projects, jobs, teamMap, projectMap, jobMap, isLoading: isLoadingWorkspace } = useWorkspace();

  const manageableProjects = projects.filter(p => {
    if (isGlobalStaff) return true;
    const t = teamMap.get(p.team);
    return t && (t.my_role === "admin" || t.my_role === "owner");
  });

  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const [statusFilter, setStatusFilter] = useState("all");
  const debouncedSearch = useDebounce(search, 500);

  // Fetch alert rules with server-side pagination
  const { data: paginatedRules, isLoading } = useQuery({
    queryKey: ["alert-rules", page, debouncedSearch, ordering, statusFilter],
    queryFn: () => getPaginatedAlertRules({ page, search: debouncedSearch, ordering, is_active: statusFilter !== "all" ? statusFilter === "true" : undefined }),
  });

  const rules = paginatedRules?.data || [];
  const totalPages = paginatedRules?.totalPages || 1;

  // Reset to first page if current page becomes out of range (e.g., after deleting items)
  useEffect(() => {
    if (!isLoading && rules.length === 0 && page > 1) {
      setPage(1);
    }
  }, [rules.length, isLoading, page]);

  const deleteMutation = useMutation({
    mutationFn: deleteAlertRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
    },
    onError: () => {
      alert("Failed to delete alert rule");
    },
  });

  const handleDelete = (id: number) => {
    if (confirm("Are you sure you want to delete this alert rule?")) {
      deleteMutation.mutate(id);
    }
  };

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number, is_active: boolean }) => updateAlertRule(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
    },
    onError: () => {
      alert("Failed to update alert rule");
    },
  });

  const handleToggle = (rule: AlertRule) => {
    toggleMutation.mutate({ id: rule.id, is_active: !rule.is_active });
  };

  const handleEdit = (rule: AlertRule) => {
    setRuleToEdit(rule);
    setModalOpen(true);
  };

  const formatMetric = (metric: string) => {
    switch (metric) {
      case "FAILURE_RATE": return "Failure Rate";
      case "RETRY_RATE": return "Retry Rate";
      case "P95_DURATION": return "P95 Duration";
      default: return metric;
    }
  };

  const formatCondition = (rule: AlertRule) => {
    const isRate = rule.metric.includes("RATE");
    return `>= ${rule.threshold}${isRate ? "%" : "ms"} over ${rule.window_minutes}m`;
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Alert Rules</h2>
          <p className="text-muted-foreground mt-1">
            Configure thresholds to automatically generate incidents when jobs fail or degrade.
          </p>
        </div>
        {manageableProjects.length > 0 && (
          <Button onClick={() => { setRuleToEdit(null); setModalOpen(true); }}>
            <Plus className="mr-2 h-4 w-4" /> Create Rule
          </Button>
        )}
      </div>

      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-card p-3 rounded-md border">
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search rules..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="flex w-full sm:w-auto gap-3">
          <div className="w-full sm:w-40">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Status">
                  {statusFilter === "all" && "All Statuses"}
                  {statusFilter === "true" && "Active"}
                  {statusFilter === "false" && "Inactive"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="true">Active</SelectItem>
                <SelectItem value="false">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-48">
            <Select value={ordering} onValueChange={setOrdering}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Sort by">
                  {ordering === "-created_at" && "Newest First"}
                  {ordering === "created_at" && "Oldest First"}
                  {ordering === "name" && "Name (A-Z)"}
                  {ordering === "severity" && "Severity (High to Low)"}
                  {ordering === "-severity" && "Severity (Low to High)"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="-created_at">Newest First</SelectItem>
                <SelectItem value="created_at">Oldest First</SelectItem>
                <SelectItem value="name">Name (A-Z)</SelectItem>
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
              <TableHead>Target (Project / Job)</TableHead>
              <TableHead>Condition</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-[80px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  <div className="flex justify-center items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading rules...
                  </div>
                </TableCell>
              </TableRow>
            ) : rules.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-32 text-center">
                  <div className="flex flex-col items-center text-muted-foreground">
                    <BellRing className="h-8 w-8 mb-2 opacity-20" />
                    <p>No alert rules configured.</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              rules.map((rule) => {
                const project = projectMap.get(rule.project);
                const job = rule.job ? jobMap.get(rule.job) : null;
                const t = project ? teamMap.get(project.team) : null;
                const canManage = isGlobalStaff || (t && (t.my_role === "admin" || t.my_role === "owner"));

                return (
                  <TableRow key={rule.id}>
                    <TableCell>
                      <div className="flex flex-col gap-1 items-start">
                        <span className="font-medium text-sm flex items-center gap-1.5">
                          {job ? job.name : "All Jobs"}
                          {job ? (
                            <Badge variant="outline" className="text-[9px] px-1 h-4">Job-specific</Badge>
                          ) : (
                            <Badge variant="secondary" className="text-[9px] px-1 h-4 bg-primary/10 text-primary">Project-wide</Badge>
                          )}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {project?.name || `Project #${rule.project}`}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <span className="text-sm">Triggers when <strong>{formatMetric(rule.metric)}</strong> {formatCondition(rule)}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={rule.severity === "CRITICAL" ? "destructive" : "secondary"}>
                        {rule.severity}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={rule.is_active ? "outline" : "secondary"} className={rule.is_active ? "border-green-500/50 text-green-600 bg-green-500/10" : ""}>
                        {rule.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {canManage && (
                        <DropdownMenu>
                          <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="h-8 w-8" />}>
                            <MoreHorizontal className="h-4 w-4" />
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleToggle(rule)} disabled={toggleMutation.isPending}>
                              {rule.is_active ? <PowerOff className="mr-2 h-4 w-4" /> : <Power className="mr-2 h-4 w-4" />}
                              {rule.is_active ? "Deactivate Rule" : "Activate Rule"}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleEdit(rule)}>
                              <Edit className="mr-2 h-4 w-4" /> Edit
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => handleDelete(rule.id)} className="text-destructive">
                              <Trash className="mr-2 h-4 w-4" /> Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
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

      <AlertRuleModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        ruleToEdit={ruleToEdit}
      />
    </div>
  );
}
