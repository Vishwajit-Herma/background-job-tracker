"use client";

import * as React from "react";
import { UserCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface UserAvatarProps {
  user?: {
    email?: string;
    first_name?: string;
    last_name?: string;
    avatar_url?: string;
  } | null;
  email?: string;
  name?: string;
  avatarUrl?: string;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  className?: string;
}

const sizeClasses = {
  xs: "h-6 w-6 text-xs",
  sm: "h-8 w-8 text-xs",
  md: "h-10 w-10 text-sm",
  lg: "h-14 w-14 text-base",
  xl: "h-20 w-20 text-lg",
};

const iconSizes = {
  xs: "h-4 w-4",
  sm: "h-5 w-5",
  md: "h-6 w-6",
  lg: "h-8 w-8",
  xl: "h-12 w-12",
};

export function UserAvatar({
  user,
  email: rawEmail,
  name: rawName,
  avatarUrl: rawAvatarUrl,
  size = "md",
  className,
}: UserAvatarProps) {
  const [hasError, setHasError] = React.useState(false);

  const email = user?.email || rawEmail || "";
  const firstName = user?.first_name || "";
  const lastName = user?.last_name || "";
  const fullName = rawName || `${firstName} ${lastName}`.trim();
  const displayName = fullName || email || "User";

  const initials = React.useMemo(() => {
    if (firstName && lastName) {
      return `${firstName[0]}${lastName[0]}`.toUpperCase();
    }
    if (displayName && displayName !== "User") {
      const parts = displayName.trim().split(" ");
      if (parts.length >= 2) {
        return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
      }
      return displayName[0].toUpperCase();
    }
    if (email) {
      return email[0].toUpperCase();
    }
    return "";
  }, [firstName, lastName, displayName, email]);

  const src = user?.avatar_url || rawAvatarUrl;

  // Reset error state if avatar URL changes
  React.useEffect(() => {
    setHasError(false);
  }, [src]);

  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-muted font-medium select-none text-muted-foreground shadow-sm ring-1 ring-border/50",
        sizeClasses[size],
        className
      )}
      title={displayName}
    >
      {src && !hasError ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={displayName}
          className="h-full w-full object-cover"
          onError={() => setHasError(true)}
        />
      ) : initials ? (
        <span className="font-semibold tracking-wider text-foreground/80">{initials}</span>
      ) : (
        <UserCircle className={cn("text-muted-foreground", iconSizes[size])} />
      )}
    </div>
  );
}
