"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPaginatedAlertRules, deleteAlertRule, AlertRule } from "@/lib/api/alerts";
import { getProjects, Project } from "@/lib/api/projects";
import { getJobs, Job } from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { BellRing, Loader2, Plus, MoreHorizontal, Edit, Trash, Activity } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AlertRuleModal } from "@/components/bjt/alerts/alert-rule-modal";
import { PaginationControls } from "@/components/bjt/pagination";

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [ruleToEdit, setRuleToEdit] = useState<AlertRule | null>(null);
  const [page, setPage] = useState(1);

  const { data: projects = [] } = useQuery<Project[]>({ queryKey: ["projects"], queryFn: () => getProjects() });
  const { data: jobs = [] } = useQuery({ queryKey: ["jobs"], queryFn: () => getJobs() });

  // Fetch alert rules with server-side pagination
  const { data: paginatedRules, isLoading } = useQuery({
    queryKey: ["alert-rules", page],
    queryFn: () => getPaginatedAlertRules({ page }),
  });

  const rules = paginatedRules?.data || [];
  const totalPages = paginatedRules?.totalPages || 1;

  // Reset to first page if current page becomes out of range (e.g., after deleting items)
  useEffect(() => {
    if (!isLoading && rules.length === 0 && page > 1) {
      setPage(1);
    }
  }, [rules.length, isLoading, page]);

  const projectMap = new Map<number, Project>(projects.map(p => [p.id, p]));
  const jobMap = new Map<number, Job>(jobs.map(j => [j.id, j]));

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
        <Button onClick={() => { setRuleToEdit(null); setModalOpen(true); }}>
          <Plus className="mr-2 h-4 w-4" /> Create Rule
        </Button>
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

                return (
                  <TableRow key={rule.id}>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium text-sm">
                          {job ? job.name : "All Jobs (Project-level)"}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {project?.name || `Project #${rule.project}`}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <span className="font-medium text-sm">{formatMetric(rule.metric)}</span>
                        <code className="text-xs text-muted-foreground bg-muted w-fit px-1.5 py-0.5 rounded">
                          {formatCondition(rule)}
                        </code>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={rule.severity === "CRITICAL" ? "destructive" : "secondary"}>
                        {rule.severity}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={rule.is_active ? "outline" : "secondary"} className={rule.is_active ? "border-green-500/50 text-green-600 bg-green-500/10" : ""}>
                        {rule.is_active ? "Active" : "Disabled"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="h-8 w-8" />}>
                          <MoreHorizontal className="h-4 w-4" />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleEdit(rule)}>
                            <Edit className="mr-2 h-4 w-4" /> Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleDelete(rule.id)} className="text-destructive">
                            <Trash className="mr-2 h-4 w-4" /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
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
