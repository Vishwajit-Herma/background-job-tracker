"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  getInAppNotifications, 
  getUnreadNotificationCount, 
  markNotificationAsRead, 
  markAllNotificationsAsRead 
} from "@/lib/api/notifications";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Bell, Check, Loader2, AlertTriangle, Info } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

export function NotificationsPopover() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const { data: unreadCount = 0 } = useQuery({
    queryKey: ["notifications-unread-count"],
    queryFn: getUnreadNotificationCount,
    refetchInterval: 60000, // Check every minute
  });

  const { data: paginated, isLoading } = useQuery({
    queryKey: ["notifications", 1],
    queryFn: () => getInAppNotifications(1),
    enabled: open, // Only fetch when popover opens
  });

  const notifications = paginated?.data || [];

  const readMutation = useMutation({
    mutationFn: markNotificationAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-unread-count"] });
    }
  });

  const readAllMutation = useMutation({
    mutationFn: markAllNotificationsAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-unread-count"] });
    }
  });

  const handleNotificationClick = (id: number, incidentEventId: number) => {
    readMutation.mutate(id);
    setOpen(false);
    // In a real app we might fetch the incident ID related to the event, 
    // but for now we route to the global incidents page, or if we had the incident ID, directly there.
    router.push(`/incidents`);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={
        <Button variant="outline" size="icon" className="ml-auto h-8 w-8 relative">
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 h-3.5 w-3.5 rounded-full bg-destructive text-[9px] font-medium text-destructive-foreground flex items-center justify-center border-2 border-background">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
          <span className="sr-only">Notifications</span>
        </Button>
      } />
      <PopoverContent align="end" className="w-[380px] p-0" sideOffset={8}>
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h4 className="font-semibold text-sm">Notifications</h4>
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
        <div className="max-h-[400px] overflow-y-auto">
          {isLoading ? (
            <div className="p-4 flex justify-center text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : notifications.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              You have no notifications.
            </div>
          ) : (
            <div className="divide-y">
              {notifications.map((notif) => (
                <div 
                  key={notif.id} 
                  className={cn(
                    "p-4 flex gap-3 hover:bg-muted/50 transition-colors cursor-pointer",
                    !notif.is_read ? "bg-primary/5" : "opacity-75"
                  )}
                  onClick={() => handleNotificationClick(notif.id, notif.incident_event)}
                >
                  <div className="mt-0.5 shrink-0">
                    {notif.title.toLowerCase().includes("critical") ? (
                      <AlertTriangle className="h-4 w-4 text-destructive" />
                    ) : (
                      <Info className="h-4 w-4 text-primary" />
                    )}
                  </div>
                  <div className="flex-1 space-y-1 min-w-0">
                    <p className={cn("text-sm font-medium leading-none", !notif.is_read && "text-foreground")}>
                      {notif.title}
                    </p>
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {notif.message}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {new Date(notif.created_at).toLocaleString()}
                    </p>
                  </div>
                  {!notif.is_read && (
                    <div className="shrink-0 flex items-center justify-center">
                      <div className="h-2 w-2 bg-primary rounded-full" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="p-2 border-t">
          <Button
            variant="ghost"
            className="w-full text-xs"
            onClick={() => {
              setOpen(false);
              router.push("/notifications");
            }}
          >
            View all notifications
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
