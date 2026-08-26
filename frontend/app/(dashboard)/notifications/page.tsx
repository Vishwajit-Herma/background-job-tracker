"use client";

import { useQuery } from "@tanstack/react-query";
import { getInAppNotifications, markAllNotificationsAsRead } from "@/lib/api/notifications";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Loader2, Bell, CheckCircle2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { PaginationControls } from "@/components/bjt/pagination";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search } from "lucide-react";
import { useDebounce } from "@/hooks/use-debounce";
import { useState } from "react";

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const debouncedSearch = useDebounce(search, 500);

  const { data: notificationsData, isLoading, isError } = useQuery({
    queryKey: ["notifications", page, debouncedSearch, ordering],
    queryFn: () => getInAppNotifications(page, { search: debouncedSearch, ordering }),
  });

  const notifications = notificationsData?.data || [];
  const totalPages = notificationsData?.totalPages || 1;

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsAsRead();
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-unread-count"] });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Notifications</h2>
          <p className="text-muted-foreground mt-1">
            View all your alerts and incident updates.
          </p>
        </div>
        <Button variant="outline" onClick={handleMarkAllRead} disabled={isLoading || notifications.length === 0}>
          <CheckCircle2 className="mr-2 h-4 w-4" />
          Mark all as read
        </Button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-card p-3 rounded-md border">
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search notifications..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="w-full sm:w-48">
          <Select value={ordering} onValueChange={setOrdering}>
            <SelectTrigger className="h-9">
              <SelectValue placeholder="Sort by">
                {ordering === "-created_at" && "Newest First"}
                {ordering === "created_at" && "Oldest First"}
                {ordering === "title" && "Title (A-Z)"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="-created_at">Newest First</SelectItem>
              <SelectItem value="created_at">Oldest First</SelectItem>
              <SelectItem value="title">Title (A-Z)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Notification</TableHead>
              <TableHead>Time</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={2} className="h-24 text-center">
                  <div className="flex justify-center items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading...
                  </div>
                </TableCell>
              </TableRow>
            ) : isError ? (
              <TableRow>
                <TableCell colSpan={2} className="h-24 text-center text-destructive">
                  Failed to load notifications.
                </TableCell>
              </TableRow>
            ) : notifications.length === 0 ? (
              <TableRow>
                <TableCell colSpan={2} className="h-32 text-center">
                  <div className="flex flex-col items-center text-muted-foreground">
                    <Bell className="h-8 w-8 mb-2 opacity-20" />
                    <p>No notifications.</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              notifications.map((notif: any) => (
                <TableRow key={notif.id} className={!notif.is_read ? "bg-muted/30" : ""}>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <span className={`font-medium ${!notif.is_read ? "text-foreground" : "text-muted-foreground"}`}>
                        {notif.title}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {notif.message}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                    {new Date(notif.created_at).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))
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
