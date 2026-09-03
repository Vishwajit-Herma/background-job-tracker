"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Loader2, Edit, Trash2, Mail, Webhook, Bell } from "lucide-react";
import { toastError, toastSuccess } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useDebounce } from "@/hooks/use-debounce";
import { useAuth } from "@/hooks/use-auth";
import { getPaginatedNotificationChannels, createNotificationChannel, updateNotificationChannel, deleteNotificationChannel, NotificationChannel } from "@/lib/api/notifications";
import { getProjects } from "@/lib/api/projects";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";

const channelSchema = z.object({
  project: z.coerce.number().min(1, "Project is required"),
  name: z.string().min(1, "Name is required"),
  type: z.enum(["WEBHOOK", "EMAIL", "IN_APP"]),
  is_active: z.boolean().default(true),
  config: z.any()
});

type ChannelFormValues = z.infer<typeof channelSchema>;

export default function AdminChannelsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const debouncedSearch = useDebounce(search, 500);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingChannel, setEditingChannel] = useState<NotificationChannel | null>(null);

  const { data: paginatedData, isLoading } = useQuery({
    queryKey: ["admin-channels", page, debouncedSearch, ordering],
    queryFn: () => getPaginatedNotificationChannels(page, { search: debouncedSearch, ordering }),
    enabled: !!user,
  });

  const { data: projects = [] } = useQuery({
    queryKey: ["admin-projects-all"],
    queryFn: () => getProjects(undefined, { search: "" }),
    enabled: !!user,
  });

  const channels = paginatedData?.data || [];

  const deleteMutation = useMutation({
    mutationFn: deleteNotificationChannel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-channels"] });
    },
  });

  const { register, handleSubmit, reset, watch, setValue, formState: { isSubmitting } } = useForm<ChannelFormValues>({
    resolver: zodResolver(channelSchema) as any,
    defaultValues: { type: "WEBHOOK", is_active: true }
  });

  const selectedType = watch("type");
  const selectedProject = watch("project");
  const recipientTarget = watch("config.recipient_target");

  const openCreateModal = () => {
    setEditingChannel(null);
    reset({
      project: projects[0]?.id || 0,
      name: "",
      type: "WEBHOOK",
      is_active: true,
      config: { url: "", secret: "", allow_insecure_http: false, recipient_target: "ALL", recipients: "" }
    });
    setIsModalOpen(true);
  };

  const openEditModal = (c: NotificationChannel) => {
    setEditingChannel(c);
    const target = c.config.recipient_target || (Array.isArray(c.config.recipients) && c.config.recipients.length > 0 ? "CUSTOM" : "ALL");
    const recipientsStr = Array.isArray(c.config.recipients) ? c.config.recipients.join(", ") : (c.config.recipients || "");

    reset({
      project: c.project,
      name: c.name,
      type: c.type,
      is_active: c.is_active,
      config: {
        ...c.config,
        recipient_target: target,
        recipients: recipientsStr,
        secret: c.config.secret ? "********" : ""
      }
    });
    setIsModalOpen(true);
  };

  const onSubmit = async (values: ChannelFormValues) => {
    try {
      if (values.type === "EMAIL") {
        const target = values.config?.recipient_target || "ALL";
        values.config.recipient_target = target;
        if (target === "CUSTOM" && typeof values.config?.recipients === "string") {
          values.config.recipients = values.config.recipients.split(",").map((s: string) => s.trim()).filter(Boolean);
        } else if (target !== "CUSTOM") {
          values.config.recipients = [];
        }
      } else if (values.type === "IN_APP") {
        values.config = {};
      }

      if (editingChannel) {
        await updateNotificationChannel(editingChannel.id, values);
        toastSuccess("Channel updated successfully");
      } else {
        await createNotificationChannel(values);
        toastSuccess("Channel created successfully");
      }
      queryClient.invalidateQueries({ queryKey: ["admin-channels"] });
      setIsModalOpen(false);
    } catch (e: any) {
      toastError("Failed to save channel", e);
    }
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Notification Channels (Admin)</h2>
          <p className="text-muted-foreground mt-1">Manage all notification channels across all projects.</p>
        </div>
        <Button onClick={openCreateModal}>
          <Plus className="mr-2 h-4 w-4" /> Create Channel
        </Button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-card p-3 rounded-md border">
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search channels..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-9" />
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

      <div className="rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Project</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Target / Config</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-[100px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow><TableCell colSpan={6} className="h-24 text-center"><Loader2 className="h-4 w-4 animate-spin mx-auto" /></TableCell></TableRow>
            ) : channels.length === 0 ? (
              <TableRow><TableCell colSpan={6} className="h-24 text-center">No channels found.</TableCell></TableRow>
            ) : (
              channels.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-medium">
                    {projects.find((p: any) => p.id === c.project)?.name || `Project #${c.project}`}
                  </TableCell>
                  <TableCell>{c.name}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      {c.type === "WEBHOOK" ? <Webhook className="h-4 w-4 text-blue-500" /> : c.type === "EMAIL" ? <Mail className="h-4 w-4 text-green-500" /> : <Bell className="h-4 w-4 text-purple-500" />}
                      {c.type}
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {c.type === "EMAIL" ? (
                      c.config.recipient_target === "ALL" ? "All Team Members" :
                      c.config.recipient_target === "ADMINS" ? "Admins & Owners Only" :
                      c.config.recipient_target === "OWNERS" ? "Owners Only" :
                      Array.isArray(c.config.recipients) ? c.config.recipients.join(", ") : "Custom"
                    ) : c.type === "IN_APP" ? (
                      "Dashboard Notifications"
                    ) : (
                      c.config.url || "-"
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={c.is_active ? "default" : "secondary"}>
                      {c.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="icon" onClick={() => openEditModal(c)}><Edit className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(c.id)}><Trash2 className="h-4 w-4 text-destructive" /></Button>
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
            <DialogTitle>{editingChannel ? "Edit Channel" : "Create Channel"}</DialogTitle>
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
              <label className="text-sm font-medium">Name</label>
              <Input {...register("name")} placeholder="Channel Name" />
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Type</label>
              <Select value={selectedType} onValueChange={(val) => setValue("type", val as any)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="WEBHOOK">Webhook</SelectItem>
                  <SelectItem value="EMAIL">Email</SelectItem>
                  <SelectItem value="IN_APP">In-App</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {selectedType === "WEBHOOK" && (
              <>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Webhook URL</label>
                  <Input {...register("config.url")} placeholder="https://..." />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Webhook Secret</label>
                  <Input type="password" {...register("config.secret")} placeholder="Minimum 16 chars" />
                </div>
              </>
            )}

            {selectedType === "EMAIL" && (
              <>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Recipient Target</label>
                  <Select
                    value={recipientTarget || "ALL"}
                    onValueChange={(val) => setValue("config.recipient_target", val)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select target" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ALL">All Team Members</SelectItem>
                      <SelectItem value="ADMINS">Admins & Owners Only</SelectItem>
                      <SelectItem value="OWNERS">Team Owners Only</SelectItem>
                      <SelectItem value="CUSTOM">Custom Email Addresses</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {recipientTarget === "CUSTOM" && (
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Recipients (comma separated)</label>
                    <Input
                      {...register("config.recipients")}
                      placeholder="user@example.com, admin@example.com"
                    />
                  </div>
                )}
              </>
            )}

            {selectedType === "IN_APP" && (
              <p className="text-xs text-muted-foreground bg-muted p-2 rounded">
                In-App channels automatically deliver alert notifications directly to the dashboard bell icon of all active team members for this project.
              </p>
            )}

            <DialogFooter>
              <Button type="submit" disabled={isSubmitting}>Save</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
