"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Loader2, Edit, Trash2 } from "lucide-react";
import { toastError, toastSuccess, getErrorMessage } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useDebounce } from "@/hooks/use-debounce";
import { useAuth } from "@/hooks/use-auth";
import { getPaginatedNotificationPolicies, createNotificationPolicy, updateNotificationPolicy, deleteNotificationPolicy, NotificationPolicy, getPaginatedNotificationChannels } from "@/lib/api/notifications";
import { getProjects } from "@/lib/api/projects";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";


const EVENT_TYPES = [
  "CREATED",
  "ASSIGNED",
  "ACKNOWLEDGED",
  "NOTE_ADDED",
  "AUTO_RESOLVED",
  "MANUALLY_RESOLVED",
  "REOPENED",
];

const policySchema = z.object({
  project: z.coerce.number().min(1, "Project is required"),
  channel: z.coerce.number().min(1, "Channel is required"),
  severity: z.enum(["CRITICAL", "DEGRADED"]),
  event_types: z.array(z.string()).min(1, "At least one event type is required"),
  is_active: z.boolean().default(true),
});

type PolicyFormValues = z.infer<typeof policySchema>;

export default function AdminPoliciesPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const debouncedSearch = useDebounce(search, 500);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<NotificationPolicy | null>(null);
  const [deletingPolicy, setDeletingPolicy] = useState<NotificationPolicy | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);

  const { data: paginatedData, isLoading, isError, error } = useQuery({
    queryKey: ["admin-policies", page, debouncedSearch, ordering],
    queryFn: () => getPaginatedNotificationPolicies(page, { search: debouncedSearch, ordering }),
    enabled: !!user,
  });

  const { data: projects = [] } = useQuery({
    queryKey: ["admin-projects-all"],
    queryFn: () => getProjects(undefined, { search: "" }),
    enabled: !!user,
  });

  const { data: channelsData } = useQuery({
    queryKey: ["admin-channels-all"],
    queryFn: () => getPaginatedNotificationChannels(1, { search: "" }),
    enabled: !!user,
  });
  const channels = channelsData?.data || [];

  const policies = paginatedData?.data || [];

  const deleteMutation = useMutation({
    mutationFn: deleteNotificationPolicy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-policies"] });
      toastSuccess("Policy deleted permanently");
      setDeletingPolicy(null);
    },
    onError: (e: any) => {
      toastError("Failed to delete policy", e);
    }
  });

  const toggleStatusMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      updateNotificationPolicy(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-policies"] });
      toastSuccess("Policy status updated");
    },
    onError: (e: any) => {
      toastError("Failed to update policy status", e);
    }
  });

  const { register, handleSubmit, reset, watch, setValue, formState: { errors, isSubmitting } } = useForm<PolicyFormValues>({
    resolver: zodResolver(policySchema) as any,
    defaultValues: { severity: "DEGRADED", is_active: true, event_types: EVENT_TYPES }
  });

  const selectedProject = watch("project");
  const selectedChannel = watch("channel");
  const selectedSeverity = watch("severity");
  const selectedEventTypes = watch("event_types") || [];
  const isActiveValue = watch("is_active");

  // Only show active channels belonging to the selected project in dropdown
  const filteredChannels = channels.filter((c: any) => c.project === selectedProject && c.is_active);

  const toggleEventType = (et: string) => {
    if (selectedEventTypes.includes(et)) {
      setValue("event_types", selectedEventTypes.filter(e => e !== et));
    } else {
      setValue("event_types", [...selectedEventTypes, et]);
    }
  };

  const openCreateModal = () => {
    setEditingPolicy(null);
    setModalError(null);
    const initialChannel = filteredChannels[0]?.id || channels.find(c => c.project === projects[0]?.id && c.is_active)?.id || 0;
    reset({ project: projects[0]?.id || 0, channel: initialChannel, severity: "DEGRADED", event_types: EVENT_TYPES, is_active: true });
    setIsModalOpen(true);
  };

  const openEditModal = (p: NotificationPolicy) => {
    let initialEventTypes = p.event_types;
    if (typeof initialEventTypes === "string") {
      try {
        initialEventTypes = JSON.parse(initialEventTypes);
      } catch (e) {}
    }
    if (!Array.isArray(initialEventTypes)) initialEventTypes = [];

    setEditingPolicy(p);
    setModalError(null);
    reset({ project: p.project, channel: p.channel, severity: p.severity, event_types: initialEventTypes, is_active: p.is_active });
    setIsModalOpen(true);
  };

  const onSubmit = async (values: PolicyFormValues) => {
    setModalError(null);
    try {
      if (editingPolicy) {
        await updateNotificationPolicy(editingPolicy.id, values);
        toastSuccess("Policy updated successfully");
      } else {
        await createNotificationPolicy(values);
        toastSuccess("Policy created successfully");
      }
      queryClient.invalidateQueries({ queryKey: ["admin-policies"] });
      setIsModalOpen(false);
    } catch (e: any) {
      const errMsg = getErrorMessage(e, "Failed to save policy");
      setModalError(errMsg);
    }
  };

  if (isError) {
    return (
      <div className="flex-1 p-8">
        <Alert variant="destructive">
          <AlertTitle>Access Restricted</AlertTitle>
          <AlertDescription>
            {getErrorMessage(error, "Failed to load notification policies. Ensure you have admin permissions.")}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Notification Policies (Admin)</h2>
          <p className="text-muted-foreground mt-1">Manage all notification policies across all projects.</p>
        </div>
        <Button onClick={openCreateModal}>
          <Plus className="mr-2 h-4 w-4" /> Create Policy
        </Button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-card p-3 rounded-md border">
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search policies..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-9" />
        </div>
        <div className="w-full sm:w-48">
          <Select value={ordering} onValueChange={setOrdering}>
            <SelectTrigger className="h-9">
              <SelectValue placeholder="Sort by">
                {ordering === "-created_at" && "Newest First"}
                {ordering === "created_at" && "Oldest First"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="-created_at">Newest First</SelectItem>
              <SelectItem value="created_at">Oldest First</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Project</TableHead>
              <TableHead>Channel</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Event Types</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-[100px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow><TableCell colSpan={6} className="h-24 text-center"><Loader2 className="h-4 w-4 animate-spin mx-auto" /></TableCell></TableRow>
            ) : policies.length === 0 ? (
              <TableRow><TableCell colSpan={6} className="h-24 text-center">No policies found.</TableCell></TableRow>
            ) : (
              policies.map((p) => {
                let ets: string[] = [];
                if (Array.isArray(p.event_types)) ets = p.event_types;
                else if (typeof p.event_types === "string") {
                  try { ets = JSON.parse(p.event_types); } catch(e){}
                }

                return (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">
                      {projects.find((proj: any) => proj.id === p.project)?.name || `Project #${p.project}`}
                    </TableCell>
                    <TableCell>
                      {channels.find((c: any) => c.id === p.channel)?.name || `Channel #${p.channel}`}
                    </TableCell>
                    <TableCell>
                      <Badge variant={p.severity === "CRITICAL" ? "destructive" : "secondary"}>
                        {p.severity}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-xs truncate">
                      {ets.join(", ") || "All"}
                    </TableCell>
                    <TableCell>
                      <Badge 
                        variant={p.is_active ? "default" : "secondary"}
                        className="cursor-pointer hover:opacity-80 transition-opacity select-none"
                        onClick={() => toggleStatusMutation.mutate({ id: p.id, is_active: !p.is_active })}
                      >
                        {p.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button variant="ghost" size="icon" onClick={() => openEditModal(p)}><Edit className="h-4 w-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => setDeletingPolicy(p)}><Trash2 className="h-4 w-4 text-destructive" /></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create / Edit Policy Modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingPolicy ? "Edit Policy" : "Create Policy"}</DialogTitle>
          </DialogHeader>

          {modalError && (
            <div className="p-3 rounded-md bg-destructive/15 text-destructive border border-destructive/30 text-sm font-medium">
              {modalError}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Project</label>
              <Select 
                value={selectedProject ? selectedProject.toString() : undefined} 
                onValueChange={(val) => { 
                  if (val) {
                    const projId = parseInt(val);
                    setValue("project", projId);
                    const activeChans = channels.filter((c: any) => c.project === projId && c.is_active);
                    if (activeChans.length > 0) {
                      setValue("channel", activeChans[0].id);
                    }
                  }
                }}
              >
                <SelectTrigger className="w-full">
                  <span data-slot="select-value" className="flex flex-1 text-left line-clamp-1">
                    {selectedProject ? projects.find((proj: any) => proj.id === selectedProject)?.name : "Select a project"}
                  </span>
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p: any) => (
                    <SelectItem key={p.id} value={p.id.toString()}>{p.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Channel (Active channels only)</label>
              <Select 
                value={selectedChannel ? selectedChannel.toString() : undefined} 
                onValueChange={(val) => { if (val && val !== "0") setValue("channel", parseInt(val)); }}
              >
                <SelectTrigger className="w-full">
                  <span data-slot="select-value" className="flex flex-1 text-left line-clamp-1">
                    {selectedChannel ? channels.find((c: any) => c.id === selectedChannel)?.name : "Select an active channel"}
                  </span>
                </SelectTrigger>
                <SelectContent>
                  {filteredChannels.length === 0 ? (
                    <SelectItem value="0" disabled>No active channels found for project</SelectItem>
                  ) : (
                    filteredChannels.map((c: any) => (
                      <SelectItem key={c.id} value={c.id.toString()}>{c.name} ({c.type})</SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Severity</label>
              <Select value={selectedSeverity} onValueChange={(val) => setValue("severity", val as any)}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select severity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="DEGRADED">Degraded (Applies to both Degraded & Critical)</SelectItem>
                  <SelectItem value="CRITICAL">Critical Only</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Trigger Event Types</label>
              <div className="flex flex-wrap gap-2 pt-1">
                {EVENT_TYPES.map((et) => {
                  const isChecked = selectedEventTypes.includes(et);
                  return (
                    <Badge
                      key={et}
                      variant={isChecked ? "default" : "outline"}
                      className="cursor-pointer select-none py-1 px-2.5 text-xs transition-colors"
                      onClick={() => toggleEventType(et)}
                    >
                      {et}
                    </Badge>
                  );
                })}
              </div>
              {errors.event_types && (
                <p className="text-xs text-destructive">{errors.event_types.message}</p>
              )}
            </div>

            <div className="flex items-center space-x-2 pt-2 border-t">
              <input
                type="checkbox"
                id="policy_is_active"
                checked={isActiveValue ?? true}
                onChange={(e) => setValue("is_active", e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer"
              />
              <label htmlFor="policy_is_active" className="text-sm font-medium cursor-pointer select-none">
                Active (Enable policy for notifications)
              </label>
            </div>

            <DialogFooter>
              <Button type="submit" disabled={isSubmitting}>Save</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Modal */}
      <Dialog open={!!deletingPolicy} onOpenChange={(open) => { if (!open) setDeletingPolicy(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Policy</DialogTitle>
            <DialogDescription>
              Are you sure you want to permanently delete this notification policy? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <Button variant="outline" onClick={() => setDeletingPolicy(null)}>Cancel</Button>
            <Button 
              variant="destructive" 
              disabled={deleteMutation.isPending}
              onClick={() => { if (deletingPolicy) deleteMutation.mutate(deletingPolicy.id); }}
            >
              {deleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete Policy
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
