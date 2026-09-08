"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  getInAppNotifications, 
  markNotificationAsRead, 
  markAllNotificationsAsRead, 
  InAppNotification 
} from "@/lib/api/notifications";
import { useUnreadNotificationCount } from "@/hooks/use-notifications";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PaginationControls } from "@/components/bjt/pagination";
import { useDebounce } from "@/hooks/use-debounce";
import { useRouter } from "next/navigation";
import { cn, formatRelativeTime } from "@/lib/utils";
import { 
  Loader2, Bell, CheckCircle2, Search, 
  AlertTriangle, UserPlus, CheckCircle, Sparkles, 
  RotateCcw, MessageSquare, Info, ChevronRight 
} from "lucide-react";

function getNotificationIcon(eventType?: string | null, severity?: string | null) {
  const type = eventType?.toUpperCase() || "";
  if (type === "CREATED") return <AlertTriangle className="h-5 w-5 text-destructive shrink-0" />;
  if (type === "ASSIGNED") return <UserPlus className="h-5 w-5 text-blue-500 shrink-0" />;
  if (type === "ACKNOWLEDGED") return <CheckCircle className="h-5 w-5 text-amber-500 shrink-0" />;
  if (type === "MANUALLY_RESOLVED" || type === "RESOLVED") return <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />;
  if (type === "AUTO_RESOLVED") return <Sparkles className="h-5 w-5 text-green-500 shrink-0" />;
  if (type === "REOPENED") return <RotateCcw className="h-5 w-5 text-purple-500 shrink-0" />;
  if (type === "NOTE_ADDED") return <MessageSquare className="h-5 w-5 text-sky-500 shrink-0" />;
  if (severity === "CRITICAL") return <AlertTriangle className="h-5 w-5 text-destructive shrink-0" />;
  return <Info className="h-5 w-5 text-primary shrink-0" />;
}

export default function NotificationsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const [readFilter, setReadFilter] = useState<string>("all");
  const debouncedSearch = useDebounce(search, 500);

  const isReadParam = readFilter === "unread" ? false : readFilter === "read" ? true : undefined;

  const { data: notificationsData, isLoading, isError } = useQuery({
    queryKey: ["notifications", page, debouncedSearch, ordering, readFilter],
    queryFn: () => getInAppNotifications(page, { 
      search: debouncedSearch, 
      ordering, 
      is_read: isReadParam 
    }),
    refetchInterval: false,
    staleTime: Infinity,
  });

  const { data: unreadCount = 0 } = useUnreadNotificationCount();

  const notifications = notificationsData?.data || [];
  const totalPages = notificationsData?.totalPages || 1;
  const totalItems = notificationsData?.totalItems || 0;

  const readMutation = useMutation({
    mutationFn: markNotificationAsRead,
    onMutate: async (id: number) => {
      await queryClient.cancelQueries({ queryKey: ["notifications"] });
      await queryClient.cancelQueries({ queryKey: ["notifications-preview"] });
      await queryClient.cancelQueries({ queryKey: ["notifications-unread-count"] });

      const previousUnread = queryClient.getQueryData<number>(["notifications-unread-count"]);

      queryClient.setQueryData<number>(["notifications-unread-count"], (old = 0) => Math.max(0, old - 1));

      queryClient.setQueriesData({ queryKey: ["notifications"] }, (old: any) => {
        if (!old) return old;
        if (Array.isArray(old)) {
          return old.map((n: InAppNotification) => (n.id === id ? { ...n, is_read: true } : n));
        }
        if (old.data && Array.isArray(old.data)) {
          return {
            ...old,
            data: old.data.map((n: InAppNotification) => (n.id === id ? { ...n, is_read: true } : n)),
          };
        }
        return old;
      });

      queryClient.setQueryData(["notifications-preview"], (old: any) => {
        if (!old) return old;
        return {
          ...old,
          data: (old.data || []).map((n: InAppNotification) => (n.id === id ? { ...n, is_read: true } : n)),
        };
      });

      return { previousUnread };
    },
    onError: (_err, _id, context) => {
      if (context?.previousUnread !== undefined) {
        queryClient.setQueryData(["notifications-unread-count"], context.previousUnread);
      }
    },
    // No onSettled invalidation: optimistic cache is correct and WebSocket
    // notification.updated event drives cache sync from the server.
  });

  const readAllMutation = useMutation({
    mutationFn: markAllNotificationsAsRead,
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["notifications"] });
      await queryClient.cancelQueries({ queryKey: ["notifications-preview"] });
      await queryClient.cancelQueries({ queryKey: ["notifications-unread-count"] });

      const previousUnread = queryClient.getQueryData<number>(["notifications-unread-count"]);

      queryClient.setQueryData<number>(["notifications-unread-count"], 0);

      queryClient.setQueriesData({ queryKey: ["notifications"] }, (old: any) => {
        if (!old) return old;
        if (Array.isArray(old)) {
          return old.map((n: InAppNotification) => ({ ...n, is_read: true }));
        }
        if (old.data && Array.isArray(old.data)) {
          return {
            ...old,
            data: old.data.map((n: InAppNotification) => ({ ...n, is_read: true })),
          };
        }
        return old;
      });

      queryClient.setQueryData(["notifications-preview"], (old: any) => {
        if (!old) return old;
        return {
          ...old,
          data: (old.data || []).map((n: InAppNotification) => ({ ...n, is_read: true })),
        };
      });

      return { previousUnread };
    },
    onError: (_err, _variables, context) => {
      if (context?.previousUnread !== undefined) {
        queryClient.setQueryData(["notifications-unread-count"], context.previousUnread);
      }
    },
    // No onSettled invalidation: optimistic cache is correct and WebSocket
    // notification.updated event drives cache sync from the server.
  });

  const handleNotificationClick = (notif: InAppNotification) => {
    if (!notif.is_read) {
      readMutation.mutate(notif.id);
    }
    if (notif.incident_id) {
      router.push(`/incidents/${notif.incident_id}`);
    } else {
      router.push(`/incidents`);
    }
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-bold tracking-tight">Notifications</h2>
            <Badge variant="secondary" className="text-xs font-normal">
              {totalItems} total · {unreadCount} unread
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1 text-sm">
            Stay up to date with incidents, alerts, and team activity.
          </p>
        </div>
        <Button 
          variant="outline" 
          onClick={() => readAllMutation.mutate()} 
          disabled={readAllMutation.isPending || unreadCount === 0}
          size="sm"
        >
          {readAllMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
          Mark all as read
        </Button>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-card p-3 rounded-lg border shadow-sm">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search notifications..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="w-full sm:w-36">
            <Select value={readFilter} onValueChange={(val) => { if (val) setReadFilter(val); }}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Status">
                  {readFilter === "all" && "All Notifications"}
                  {readFilter === "unread" && "Unread Only"}
                  {readFilter === "read" && "Read Only"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Notifications</SelectItem>
                <SelectItem value="unread">Unread Only</SelectItem>
                <SelectItem value="read">Read Only</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="w-full sm:w-44">
            <Select value={ordering} onValueChange={(val) => { if (val) setOrdering(val); }}>
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
      </div>

      {/* Notification List Container */}
      <div className="rounded-lg border bg-card shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="h-40 flex items-center justify-center text-muted-foreground gap-2">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading notifications...
          </div>
        ) : isError ? (
          <div className="h-40 flex items-center justify-center text-destructive">
            Failed to load notifications.
          </div>
        ) : notifications.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground flex flex-col items-center">
            <Bell className="h-10 w-10 mb-3 opacity-20" />
            <p className="font-medium text-base">No notifications found</p>
            <p className="text-xs text-muted-foreground mt-1">
              {readFilter === "unread" ? "You have no unread notifications." : "You're all caught up!"}
            </p>
          </div>
        ) : (
          <div className="divide-y">
            {notifications.map((notif: InAppNotification) => {
              return (
                <div
                  key={notif.id}
                  onClick={() => handleNotificationClick(notif)}
                  className={cn(
                    "p-4 sm:p-5 flex items-start gap-4 hover:bg-muted/40 transition-all cursor-pointer relative group",
                    !notif.is_read ? "bg-primary/[0.03] dark:bg-primary/[0.06] border-l-4 border-l-primary" : "opacity-80"
                  )}
                >
                  <div className="mt-1 p-2 rounded-full bg-background border shrink-0 shadow-xs">
                    {getNotificationIcon(notif.event_type, notif.incident_severity)}
                  </div>

                  <div className="flex-1 min-w-0 space-y-1.5">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        {!notif.is_read && (
                          <span className="h-2 w-2 rounded-full bg-primary inline-block shrink-0" />
                        )}
                        <h4 className={cn("text-sm font-semibold tracking-tight", !notif.is_read ? "text-foreground font-bold" : "text-muted-foreground")}>
                          {notif.title}
                        </h4>
                        {notif.incident_severity && (
                          <Badge variant="outline" className={cn("text-[10px] uppercase font-bold py-0 h-4", notif.incident_severity === "CRITICAL" ? "text-destructive border-destructive/40 bg-destructive/5" : "text-amber-600 border-amber-500/40 bg-amber-500/5")}>
                            {notif.incident_severity}
                          </Badge>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground shrink-0 font-normal" title={new Date(notif.created_at).toLocaleString()}>
                        {formatRelativeTime(notif.created_at)}
                      </span>
                    </div>

                    <p className="text-sm text-muted-foreground leading-normal break-words">
                      {notif.message}
                    </p>

                    {(notif.project_name || notif.job_name) && (
                      <div className="pt-1 flex items-center gap-2 text-xs text-muted-foreground font-mono">
                        <span>{notif.project_name}</span>
                        {notif.job_name && (
                          <>
                            <span>·</span>
                            <span>{notif.job_name}</span>
                          </>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="self-center shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                    <ChevronRight className="h-5 w-5" />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {totalPages > 1 && (
          <div className="px-4 py-3 border-t bg-muted/10">
            <PaginationControls page={page} totalPages={totalPages} setPage={setPage} />
          </div>
        )}
      </div>
    </div>
  );
}
