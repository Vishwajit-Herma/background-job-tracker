"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Loader2, Edit, Trash2, ShieldCheck } from "lucide-react";
import { toastError, toastSuccess } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useDebounce } from "@/hooks/use-debounce";
import { useAuth } from "@/hooks/use-auth";
import { useRouter } from "next/navigation";
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
  const router = useRouter();

  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const debouncedSearch = useDebounce(search, 500);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<NotificationPolicy | null>(null);

  const { data: paginatedData, isLoading } = useQuery({
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
  const totalPages = paginatedData?.totalPages || 1;

  const deleteMutation = useMutation({
    mutationFn: deleteNotificationPolicy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-policies"] });
    },
  });

  const { register, handleSubmit, reset, watch, setValue, formState: { errors, isSubmitting } } = useForm<PolicyFormValues>({
    resolver: zodResolver(policySchema) as any,
    defaultValues: { severity: "DEGRADED", is_active: true, event_types: EVENT_TYPES }
  });

  const selectedProject = watch("project");
  const selectedChannel = watch("channel");
  const selectedSeverity = watch("severity");
  const selectedEventTypes = watch("event_types") || [];

  const filteredChannels = channels.filter((c: any) => c.project === selectedProject);

  const toggleEventType = (et: string) => {
    if (selectedEventTypes.includes(et)) {
      setValue("event_types", selectedEventTypes.filter(e => e !== et));
    } else {
      setValue("event_types", [...selectedEventTypes, et]);
    }
  };

  const openCreateModal = () => {
    setEditingPolicy(null);
    reset({ project: projects[0]?.id || 0, channel: channels[0]?.id || 0, severity: "DEGRADED", event_types: EVENT_TYPES, is_active: true });
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
    reset({ project: p.project, channel: p.channel, severity: p.severity, event_types: initialEventTypes, is_active: p.is_active });
    setIsModalOpen(true);
  };

  const onSubmit = async (values: PolicyFormValues) => {
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
      toastError("Failed to save policy", e);
    }
  };


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
              <TableHead>Channel ID</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-[100px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow><TableCell colSpan={5} className="h-24 text-center"><Loader2 className="h-4 w-4 animate-spin mx-auto" /></TableCell></TableRow>
            ) : policies.length === 0 ? (
              <TableRow><TableCell colSpan={5} className="h-24 text-center">No policies found.</TableCell></TableRow>
            ) : (
              policies.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">
                    {projects.find((proj: any) => proj.id === p.project)?.name || `Project #${p.project}`}
                  </TableCell>
                  <TableCell>
                    {channels.find((c: any) => c.id === p.channel)?.name || `Channel #${p.channel}`}
                  </TableCell>
                  <TableCell>
                    <Badge variant={p.severity === "CRITICAL" ? "destructive" : "default"}>{p.severity}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={p.is_active ? "default" : "secondary"}>
                      {p.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="icon" onClick={() => openEditModal(p)}><Edit className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(p.id)}><Trash2 className="h-4 w-4 text-destructive" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingPolicy ? "Edit Policy" : "Create Policy"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Project</label>
              <Select 
                value={selectedProject ? selectedProject.toString() : undefined} 
                onValueChange={(val) => { if (val) setValue("project", parseInt(val)); }}
              >
                <SelectTrigger>
                  <span data-slot="select-value" className="flex flex-1 text-left line-clamp-1">
                    {selectedProject ? projects.find((p: any) => p.id === selectedProject)?.name : "Select a project"}
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
              <label className="text-sm font-medium">Channel</label>
              <Select 
                value={selectedChannel ? selectedChannel.toString() : undefined} 
                onValueChange={(val) => { if (val) setValue("channel", parseInt(val)); }}
              >
                <SelectTrigger>
                  <span data-slot="select-value" className="flex flex-1 text-left line-clamp-1">
                    {selectedChannel ? filteredChannels.find((c: any) => c.id === selectedChannel)?.name : "Select a channel"}
                  </span>
                </SelectTrigger>
                <SelectContent>
                  {filteredChannels.map((c: any) => (
                    <SelectItem key={c.id} value={c.id.toString()}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Severity</label>
              <Select value={selectedSeverity} onValueChange={(val) => setValue("severity", val as any)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select severity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CRITICAL">Critical</SelectItem>
                  <SelectItem value="DEGRADED">Degraded</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Event Types</label>
              <div className="flex flex-col space-y-3">
                {EVENT_TYPES.map((et) => (
                  <div key={et} className="flex items-start space-x-2">
                    <input 
                      type="checkbox"
                      id={et} 
                      className="h-4 w-4 rounded border-gray-300 mt-0.5 flex-shrink-0"
                      checked={selectedEventTypes.includes(et)} 
                      onChange={() => toggleEventType(et)} 
                    />
                    <label htmlFor={et} className="text-sm font-medium leading-tight peer-disabled:cursor-not-allowed peer-disabled:opacity-70 break-words">
                      {et}
                    </label>
                  </div>
                ))}
              </div>
            </div>

            <DialogFooter>
              <Button type="submit" disabled={isSubmitting}>Save</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
