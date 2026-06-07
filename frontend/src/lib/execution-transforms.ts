import type { ExecutionItem } from "@/lib/api/types";
import { formatAction } from "@/lib/transforms";

export type ExecutionStatus = "success" | "failed" | "rolled_back" | "pending";
export type ExecutionDateRange = "7d" | "30d" | "90d" | "365d" | "all";

export const EXECUTION_DATE_RANGE_LABELS: Record<ExecutionDateRange, string> = {
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  "90d": "Last 90 days",
  "365d": "Last 12 months",
  all: "All time",
};

export const STATUS_LABELS: Record<ExecutionStatus, string> = {
  success: "Success",
  failed: "Failed",
  rolled_back: "Rolled Back",
  pending: "Pending",
};

export const STATUS_COLORS: Record<ExecutionStatus, string> = {
  success: "#3FB950",
  failed: "#F85149",
  rolled_back: "#F0B429",
  pending: "#58A6FF",
};

export const ACTION_COLORS: Record<string, string> = {
  terminate: "#F85149",
  resize: "#7745FF",
  stop: "#58A6FF",
  snapshot_and_delete: "#F0B429",
};

export function isWithinDateRange(timestamp: string, range: ExecutionDateRange): boolean {
  if (range === "all") return true;
  const days = range === "7d" ? 7 : range === "30d" ? 30 : range === "90d" ? 90 : 365;
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return new Date(timestamp).getTime() >= cutoff;
}

export function computeExecutionSummary(executions: ExecutionItem[]) {
  const completed = executions.filter((item) => item.status !== "pending");
  const rollbackCount = executions.filter(
    (item) => (item.rollback_steps ?? []).length > 0
  ).length;

  return {
    totalExecutions: completed.length,
    successful: completed.filter((item) => item.status === "success").length,
    failed: completed.filter((item) => item.status === "failed").length,
    rolledBack: completed.filter((item) => item.status === "rolled_back").length,
    pending: executions.filter((item) => item.status === "pending").length,
    rollbacksGenerated: rollbackCount,
    totalSavings: completed.reduce((sum, item) => sum + (item.estimated_savings ?? 0), 0),
  };
}

export function buildStatusDistribution(executions: ExecutionItem[]) {
  const statuses: ExecutionStatus[] = ["success", "failed", "rolled_back", "pending"];
  return statuses
    .map((status) => ({
      status,
      label: STATUS_LABELS[status],
      count: executions.filter((item) => item.status === status).length,
      fill: STATUS_COLORS[status],
    }))
    .filter((item) => item.count > 0);
}

export function buildActionTypeDistribution(executions: ExecutionItem[]) {
  const map = new Map<string, number>();
  for (const item of executions) {
    map.set(item.action, (map.get(item.action) ?? 0) + 1);
  }

  return Array.from(map.entries())
    .map(([action, count]) => ({
      action,
      label: formatAction(action),
      count,
      fill: ACTION_COLORS[action] ?? "#6E7681",
    }))
    .sort((a, b) => b.count - a.count);
}

export function buildExecutionTimeline(executions: ExecutionItem[]) {
  const completed = executions
    .filter((item) => item.status !== "pending")
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  return completed.map((item, index) => ({
    time: new Date(item.timestamp).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }),
    cumulative: index + 1,
    status: item.status,
    resource_id: item.resource_id,
  }));
}

export function buildSuccessRateTrend(executions: ExecutionItem[]) {
  const completed = executions
    .filter((item) => item.status !== "pending")
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  if (completed.length === 0) return [];

  let successCount = 0;
  return completed.map((item, index) => {
    if (item.status === "success") successCount += 1;
    const rate = Math.round((successCount / (index + 1)) * 1000) / 10;
    return {
      index: index + 1,
      label: `#${index + 1}`,
      successRate: rate,
      status: item.status,
    };
  });
}

export function filterExecutions(
  executions: ExecutionItem[],
  search: string,
  statusFilter: string,
  actionFilter: string,
  dateRange: ExecutionDateRange
): ExecutionItem[] {
  const query = search.trim().toLowerCase();

  return executions.filter((item) => {
    const matchesSearch =
      query === "" ||
      item.execution_id.toLowerCase().includes(query) ||
      item.resource_id.toLowerCase().includes(query) ||
      item.action.toLowerCase().includes(query) ||
      item.approval_id.toLowerCase().includes(query);

    const matchesStatus = statusFilter === "all" || item.status === statusFilter;
    const matchesAction = actionFilter === "all" || item.action === actionFilter;
    const matchesDate = isWithinDateRange(item.timestamp, dateRange);

    return matchesSearch && matchesStatus && matchesAction && matchesDate;
  });
}

export function executionStatusBadgeVariant(
  status: string
): "success" | "destructive" | "warning" | "default" | "secondary" {
  if (status === "success") return "success";
  if (status === "failed") return "destructive";
  if (status === "rolled_back") return "warning";
  if (status === "pending") return "default";
  return "secondary";
}

export function parseActivityEvents(executions: ExecutionItem[]): ActivityEvent[] {
  const events: ActivityEvent[] = [];

  for (const execution of executions) {
    const logEvents = extractEventsFromLogs(execution);
    events.push(...logEvents);

    if ((execution.rollback_steps ?? []).length > 0 && execution.status !== "pending") {
      events.push({
        id: `${execution.execution_id}-rollback`,
        execution_id: execution.execution_id,
        resource_id: execution.resource_id,
        message: "Rollback generated",
        timestamp: execution.timestamp,
        status: execution.status,
        type: "rollback",
      });
    }
  }

  return events.sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );
}

export interface ActivityEvent {
  id: string;
  execution_id: string;
  resource_id: string;
  message: string;
  timestamp: string;
  status: string;
  type: "info" | "success" | "error" | "rollback";
}

function extractEventsFromLogs(execution: ExecutionItem): ActivityEvent[] {
  const events: ActivityEvent[] = [];

  for (const line of execution.logs ?? []) {
    const message = humanizeLogLine(line);
    if (!message) continue;

    events.push({
      id: `${execution.execution_id}-${events.length}`,
      execution_id: execution.execution_id,
      resource_id: execution.resource_id,
      message,
      timestamp: execution.timestamp,
      status: execution.status,
      type: line.includes("[ERROR]") ? "error" : line.includes("success") ? "success" : "info",
    });
  }

  if (events.length === 0 && execution.status === "pending") {
    events.push({
      id: `${execution.execution_id}-pending`,
      execution_id: execution.execution_id,
      resource_id: execution.resource_id,
      message: "Awaiting executor dispatch",
      timestamp: execution.timestamp,
      status: execution.status,
      type: "info",
    });
  }

  return events;
}

function humanizeLogLine(line: string): string | null {
  const normalized = line.replace(/^\[(INFO|ERROR|WARN)\]\s*/, "").trim();
  if (!normalized || normalized.startsWith("Execution ID:") || normalized.startsWith("Mode:")) {
    return null;
  }
  if (normalized.startsWith("Approval ID:")) return null;
  if (normalized.startsWith("Planned Steps:")) return null;
  if (normalized.includes("Rollback plan prepared")) return "Rollback plan prepared";
  if (normalized.includes("Simulation complete")) return "Simulation complete";

  if (/snapshot created/i.test(normalized)) return "Snapshot created";
  if (/backup snapshot created/i.test(normalized)) return "Backup snapshot created";
  if (/creating snapshot/i.test(normalized)) return "Creating snapshot";
  if (/instance stopped/i.test(normalized)) return "Instance stopped";
  if (/stopping instance/i.test(normalized)) return "Stopping instance";
  if (/volume deleted/i.test(normalized)) return "Volume deleted";
  if (/deleting ebs volume/i.test(normalized)) return "Deleting EBS volume";
  if (/resource terminated/i.test(normalized)) return "Resource terminated";
  if (/terminating instance/i.test(normalized)) return "Terminating instance";
  if (/validation complete/i.test(normalized)) return "Validation complete";
  if (/restart/i.test(normalized)) return "Instance restarted";

  if (normalized.startsWith("Starting ")) {
    return normalized.replace("Starting ", "").replace(" workflow for", " started");
  }

  return normalized.length > 80 ? `${normalized.slice(0, 77)}...` : normalized;
}

export function logsToText(execution: ExecutionItem): string {
  if ((execution.logs ?? []).length > 0) {
    return (execution.logs ?? []).join("\n");
  }

  const lines = [
    `Execution ID: ${execution.execution_id}`,
    `Resource: ${execution.resource_id}`,
    `Action: ${execution.action}`,
    `Status: ${execution.status}`,
    `Timestamp: ${execution.timestamp}`,
    "",
    "Execution Steps:",
    ...(execution.execution_steps ?? []).map((step, index) => `${index + 1}. ${step}`),
  ];

  if (execution.status === "pending") {
    lines.push("", "Awaiting executor dispatch — no logs recorded yet.");
  }

  return lines.join("\n");
}

export function downloadLogs(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
