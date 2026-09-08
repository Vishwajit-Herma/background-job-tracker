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
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Bell, Check, Loader2, AlertTriangle, 
  UserPlus, CheckCircle, CheckCircle2, Sparkles, 
  RotateCcw, MessageSquare, Info, ArrowRight 
} from "lucide-react";
import { useRouter } from "next/navigation";
import { cn, formatRelativeTime } from "@/lib/utils";

function getNotificationIcon(eventType?: string | null, severity?: string | null) {
  const type = eventType?.toUpperCase() || "";
  if (type === "CREATED") return <AlertTriangle className="h-4 w-4 text-destructive shrink-0" />;
  if (type === "ASSIGNED") return <UserPlus className="h-4 w-4 text-blue-500 shrink-0" />;
  if (type === "ACKNOWLEDGED") return <CheckCircle className="h-4 w-4 text-amber-500 shrink-0" />;
  if (type === "MANUALLY_RESOLVED" || type === "RESOLVED") return <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />;
  if (type === "AUTO_RESOLVED") return <Sparkles className="h-4 w-4 text-green-500 shrink-0" />;
  if (type === "REOPENED") return <RotateCcw className="h-4 w-4 text-purple-500 shrink-0" />;
  if (type === "NOTE_ADDED") return <MessageSquare className="h-4 w-4 text-sky-500 shrink-0" />;
  if (severity === "CRITICAL") return <AlertTriangle className="h-4 w-4 text-destructive shrink-0" />;
  return <Info className="h-4 w-4 text-primary shrink-0" />;
}

export function NotificationsPopover() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const { data: unreadCount = 0 } = useUnreadNotificationCount();

  const { data: paginated, isLoading } = useQuery({
    queryKey: ["notifications-preview"],
    queryFn: () => getInAppNotifications(1, { ordering: "-created_at" }),
    refetchInterval: false,
    staleTime: Infinity,
  });

  const notifications = paginated?.data || [];

  const readMutation = useMutation({
    mutationFn: markNotificationAsRead,
    onMutate: async (id: number) => {
      await queryClient.cancelQueries({ queryKey: ["notifications-preview"] });
      await queryClient.cancelQueries({ queryKey: ["notifications"] });
      await queryClient.cancelQueries({ queryKey: ["notifications-unread-count"] });

      const previousPreview = queryClient.getQueryData(["notifications-preview"]);
      const previousUnread = queryClient.getQueryData<number>(["notifications-unread-count"]);

      queryClient.setQueryData(["notifications-preview"], (old: any) => {
        if (!old) return old;
        const updatedData = (old.data || []).map((n: InAppNotification) =>
          n.id === id ? { ...n, is_read: true } : n
        );
        return { ...old, data: updatedData };
      });

      queryClient.setQueryData<number>(["notifications-unread-count"], (old = 0) => Math.max(0, old - 1));

      return { previousPreview, previousUnread };
    },
    onError: (_err, _id, context) => {
      if (context?.previousPreview) {
        queryClient.setQueryData(["notifications-preview"], context.previousPreview);
      }
      if (context?.previousUnread !== undefined) {
        queryClient.setQueryData(["notifications-unread-count"], context.previousUnread);
      }
    },
    // No onSettled invalidation: optimistic cache is correct and WebSocket
    // notification.updated event will trigger a refetch if the server state diverges.
  });

  const readAllMutation = useMutation({
    mutationFn: markAllNotificationsAsRead,
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["notifications-preview"] });
      await queryClient.cancelQueries({ queryKey: ["notifications"] });
      await queryClient.cancelQueries({ queryKey: ["notifications-unread-count"] });

      const previousPreview = queryClient.getQueryData(["notifications-preview"]);
      const previousUnread = queryClient.getQueryData<number>(["notifications-unread-count"]);

      queryClient.setQueryData<number>(["notifications-unread-count"], 0);

      queryClient.setQueryData(["notifications-preview"], (old: any) => {
        if (!old) return old;
        const updatedData = (old.data || []).map((n: InAppNotification) => ({ ...n, is_read: true }));
        return { ...old, data: updatedData };
      });

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

      return { previousPreview, previousUnread };
    },
    onError: (_err, _variables, context) => {
      if (context?.previousPreview) {
        queryClient.setQueryData(["notifications-preview"], context.previousPreview);
      }
      if (context?.previousUnread !== undefined) {
        queryClient.setQueryData(["notifications-unread-count"], context.previousUnread);
      }
    },
    // No onSettled invalidation: optimistic cache is correct and WebSocket
    // notification.updated event will trigger a refetch if the server state diverges.
  });

  const handleNotificationClick = (notif: InAppNotification) => {
    if (!notif.is_read) {
      readMutation.mutate(notif.id);
    }
    setOpen(false);
    if (notif.incident_id) {
      router.push(`/incidents/${notif.incident_id}`);
    } else {
      router.push(`/incidents`);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={
        <Button variant="outline" size="icon" className="ml-auto h-8 w-8 relative">
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 h-4 min-w-4 px-1 rounded-full bg-destructive text-[9px] font-bold text-destructive-foreground flex items-center justify-center border-2 border-background">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
          <span className="sr-only">Notifications</span>
        </Button>
      } />
      <PopoverContent align="end" className="w-[380px] p-0 shadow-lg" sideOffset={8}>
        <div className="flex items-center justify-between px-4 py-3 border-b bg-card">
          <div className="flex items-center gap-2">
            <h4 className="font-semibold text-sm">Notifications</h4>
            {unreadCount > 0 && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 bg-primary/10 text-primary">
                {unreadCount} unread
              </Badge>
            )}
          </div>
          {unreadCount > 0 && (
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => readAllMutation.mutate()}
              disabled={readAllMutation.isPending}
              className="h-auto p-0 text-xs text-muted-foreground hover:text-primary"
            >
              <Check className="mr-1 h-3 w-3" /> Mark all read
            </Button>
          )}
        </div>
        <div className="max-h-[380px] overflow-y-auto divide-y">
          {isLoading ? (
            <div className="p-6 flex justify-center text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : notifications.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground flex flex-col items-center">
              <Bell className="h-8 w-8 mb-2 opacity-20" />
              <p>No notifications yet.</p>
            </div>
          ) : (
            notifications.map((notif) => (
              <div 
                key={notif.id} 
                className={cn(
                  "p-3.5 flex gap-3 hover:bg-muted/50 transition-colors cursor-pointer relative",
                  !notif.is_read ? "bg-primary/5 font-medium" : "opacity-80"
                )}
                onClick={() => handleNotificationClick(notif)}
              >
                <div className="mt-0.5 shrink-0">
                  {getNotificationIcon(notif.event_type, notif.incident_severity)}
                </div>
                <div className="flex-1 space-y-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className={cn("text-xs font-semibold truncate", !notif.is_read ? "text-foreground" : "text-muted-foreground")}>
                      {notif.title}
                    </p>
                    <span className="text-[10px] text-muted-foreground shrink-0" title={new Date(notif.created_at).toLocaleString()}>
                      {formatRelativeTime(notif.created_at)}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                    {notif.message}
                  </p>
                  {(notif.project_name || notif.job_name) && (
                    <p className="text-[10px] text-muted-foreground font-mono truncate pt-0.5">
                      {notif.project_name}{notif.job_name ? ` · ${notif.job_name}` : ""}
                    </p>
                  )}
                </div>
                {!notif.is_read && (
                  <div className="shrink-0 self-center">
                    <div className="h-2 w-2 bg-primary rounded-full" />
                  </div>
                )}
              </div>
            ))
          )}
        </div>
        <div className="p-2 border-t bg-card">
          <Button
            variant="ghost"
            className="w-full text-xs justify-between"
            onClick={() => {
              setOpen(false);
              router.push("/notifications");
            }}
          >
            <span>View all notifications</span>
            <ArrowRight className="h-3.5 w-3.5 ml-1 opacity-70" />
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
