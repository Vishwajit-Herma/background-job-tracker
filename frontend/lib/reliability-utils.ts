import { format, formatDistanceToNow } from "date-fns";

/**
 * Adaptively formats milliseconds into human-readable duration strings.
 * e.g. 420 ms, 1.8 s, 2m 14s, 1h 12m
 */
export function formatDurationMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || isNaN(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;

  const totalSeconds = ms / 1000;
  if (totalSeconds < 60) return `${totalSeconds.toFixed(1)} s`;

  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = Math.round(totalSeconds % 60);

  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes} min`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours} hrs`;
}

/**
 * Adaptively formats seconds into human-readable duration strings.
 * e.g. 30s, 5 minutes, 1.5 hours
 */
export function formatDurationSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return "—";
  if (seconds < 60) return `${Math.round(seconds)} sec`;

  const minutes = Math.floor(seconds / 60);
  const remSec = Math.round(seconds % 60);

  if (minutes < 60) {
    if (remSec === 0) return `${minutes} ${minutes === 1 ? "minute" : "minutes"}`;
    return `${minutes}m ${remSec}s`;
  }

  const hours = Math.floor(minutes / 60);
  const remMin = minutes % 60;
  if (remMin === 0) return `${hours} ${hours === 1 ? "hour" : "hours"}`;
  return `${hours}h ${remMin}m`;
}

/**
 * Formats a timestamp into relative time with full date/time subtext.
 */
export function formatReliabilityTime(isoString: string | null | undefined): {
  relative: string;
  exact: string;
} {
  if (!isoString) return { relative: "—", exact: "—" };
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return { relative: "—", exact: "—" };

    const now = Date.now();
    const isFuture = date.getTime() > now;
    const distance = formatDistanceToNow(date, { addSuffix: true });

    return {
      relative: isFuture ? distance : distance,
      exact: format(date, "MMM d, yyyy · h:mm:ss a"),
    };
  } catch {
    return { relative: "—", exact: "—" };
  }
}
