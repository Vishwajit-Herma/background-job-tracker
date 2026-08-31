"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Loader2, Edit, Trash2, Mail, Webhook, ShieldAlert } from "lucide-react";
import { toastError, toastSuccess } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useDebounce } from "@/hooks/use-debounce";
import { useAuth } from "@/hooks/use-auth";
import { useRouter } from "next/navigation";
import { getPaginatedNotificationChannels, createNotificationChannel, updateNotificationChannel, deleteNotificationChannel, NotificationChannel } from "@/lib/api/notifications";
import { getProjects } from "@/lib/api/projects";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";

const channelSchema = z.object({
  project: z.coerce.number().min(1, "Project is required"),
  name: z.string().min(1, "Name is required"),
  type: z.enum(["WEBHOOK", "EMAIL"]),
  is_active: z.boolean().default(true),
  config: z.any()
});

type ChannelFormValues = z.infer<typeof channelSchema>;

export default function AdminChannelsPage() {
  const { user } = useAuth();
  const router = useRouter();


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
  const totalPages = paginatedData?.totalPages || 1;

  const deleteMutation = useMutation({
    mutationFn: deleteNotificationChannel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-channels"] });
    },
  });

  const { register, handleSubmit, reset, watch, setValue, formState: { errors, isSubmitting } } = useForm<ChannelFormValues>({
    resolver: zodResolver(channelSchema) as any,
    defaultValues: { type: "WEBHOOK", is_active: true }
  });

  const selectedType = watch("type");
  const selectedProject = watch("project");

  const openCreateModal = () => {
    setEditingChannel(null);
    reset({ project: projects[0]?.id || 0, type: "WEBHOOK", is_active: true, config: { url: "", secret: "", allow_insecure_http: false } });
    setIsModalOpen(true);
  };

  const openEditModal = (c: NotificationChannel) => {
    setEditingChannel(c);
    reset({ project: c.project, name: c.name, type: c.type, is_active: c.is_active, config: { ...c.config, secret: c.config.secret ? "********" : "" } });
    setIsModalOpen(true);
  };

  const onSubmit = async (values: ChannelFormValues) => {
    try {
      if (values.type === "EMAIL" && typeof values.config?.recipients === "string") {
        values.config.recipients = values.config.recipients.split(",").map((s: string) => s.trim()).filter(Boolean);
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
              <TableHead>Status</TableHead>
              <TableHead className="w-[100px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow><TableCell colSpan={5} className="h-24 text-center"><Loader2 className="h-4 w-4 animate-spin mx-auto" /></TableCell></TableRow>
            ) : channels.length === 0 ? (
              <TableRow><TableCell colSpan={5} className="h-24 text-center">No channels found.</TableCell></TableRow>
            ) : (
              channels.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-medium">
                    {projects.find((p: any) => p.id === c.project)?.name || `Project #${c.project}`}
                  </TableCell>
                  <TableCell>{c.name}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      {c.type === "WEBHOOK" ? <Webhook className="h-4 w-4 text-blue-500" /> : <Mail className="h-4 w-4 text-green-500" />}
                      {c.type}
                    </div>
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
              <div className="space-y-1">
                <label className="text-sm font-medium">Recipients (comma separated)</label>
                <Input {...register("config.recipients")} placeholder="user@example.com, admin@example.com" />
              </div>
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
