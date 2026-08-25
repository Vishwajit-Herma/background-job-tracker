import { Badge } from "@/components/ui/badge";

type HealthStatus = "HEALTHY" | "DEGRADED" | "CRITICAL" | "INFO";
type Severity = "INFO" | "WARNING" | "CRITICAL";

export function HealthBadge({ status }: { status: HealthStatus }) {
  const variantMap: Record<HealthStatus, "success" | "warning" | "destructive" | "info"> = {
    HEALTHY: "success",
    DEGRADED: "warning",
    CRITICAL: "destructive",
    INFO: "info",
  };
  return <Badge variant={variantMap[status]}>{status}</Badge>;
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const variantMap: Record<Severity, "info" | "warning" | "destructive"> = {
    INFO: "info",
    WARNING: "warning",
    CRITICAL: "destructive",
  };
  return <Badge variant={variantMap[severity]}>{severity}</Badge>;
}
