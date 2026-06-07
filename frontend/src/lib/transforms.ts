import type {
  ApprovalItem,
  AuditResultItem,
  ExecutionItem,
  ResourceItem,
  RiskAssessmentItem,
} from "@/lib/api/types";

export function computeRiskStats(risk: RiskAssessmentItem[]) {
  const stats = {
    total: risk.length,
    low: 0,
    medium: 0,
    high: 0,
    safe_to_remediate: 0,
    manual_review: 0,
    do_not_remediate: 0,
    avg_risk_score: 0,
  };

  if (!risk.length) return stats;

  let scoreSum = 0;
  for (const item of risk) {
    if (item.risk_level === "low") stats.low += 1;
    if (item.risk_level === "medium") stats.medium += 1;
    if (item.risk_level === "high") stats.high += 1;
    if (item.recommendation === "Safe To Remediate") stats.safe_to_remediate += 1;
    if (item.recommendation === "Manual Review Required") stats.manual_review += 1;
    if (item.recommendation === "Do Not Remediate") stats.do_not_remediate += 1;
    scoreSum += item.risk_score;
  }

  stats.avg_risk_score = Math.round((scoreSum / risk.length) * 10) / 10;
  return stats;
}

export function computeRiskDistribution(risk: RiskAssessmentItem[]) {
  const stats = computeRiskStats(risk);
  return [
    { level: "low" as const, count: stats.low },
    { level: "medium" as const, count: stats.medium },
    { level: "high" as const, count: stats.high },
  ];
}

export type ApprovalStatus = "pending" | "approved" | "rejected" | "executed";

export function computeApprovalStats(approvals: ApprovalItem[]) {
  const stats = {
    total: approvals.length,
    pending: 0,
    approved: 0,
    rejected: 0,
    executed: 0,
    pending_savings: 0,
    approved_savings: 0,
  };

  for (const item of approvals) {
    if (item.status === "pending") stats.pending += 1;
    if (item.status === "approved") stats.approved += 1;
    if (item.status === "rejected") stats.rejected += 1;
    if (item.status === "executed") stats.executed += 1;
    if (item.status === "pending") stats.pending_savings += item.estimated_savings;
    if (item.status === "approved" || item.status === "executed") {
      stats.approved_savings += item.estimated_savings;
    }
  }

  stats.pending_savings = Math.round(stats.pending_savings * 100) / 100;
  stats.approved_savings = Math.round(stats.approved_savings * 100) / 100;
  return stats;
}

export function buildApprovalHistory(approvals: ApprovalItem[]) {
  return approvals
    .filter((item) => item.status !== "pending" && item.reviewed_by)
    .map((item) => ({
      approval_id: item.approval_id,
      resource_id: item.resource_id,
      previous_status: "pending" as const,
      new_status: item.status as "approved" | "rejected" | "executed",
      timestamp: item.updated_at,
      actor: item.reviewed_by ?? "unknown",
      notes: item.review_notes,
    }))
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
}

export function computeAuditSummary(audit: AuditResultItem[]) {
  return {
    totalMonthlyCost: audit.reduce((sum, item) => sum + item.monthly_cost, 0),
    totalAnnualCost: audit.reduce((sum, item) => sum + item.annual_cost, 0),
    potentialAnnualSavings: audit.reduce((sum, item) => sum + item.potential_annual_savings, 0),
    potentialMonthlySavings: audit.reduce((sum, item) => sum + item.potential_monthly_savings, 0),
    safeToRemediate: audit.filter((item) => item.recommendation === "Safe To Remediate").length,
    manualReview: audit.filter((item) => item.recommendation === "Manual Review Required").length,
    doNotRemediate: audit.filter((item) => item.recommendation === "Do Not Remediate").length,
  };
}

export function savingsByRecommendation(audit: AuditResultItem[]) {
  const map = new Map<string, number>();
  for (const item of audit) {
    map.set(item.recommendation, (map.get(item.recommendation) ?? 0) + item.potential_annual_savings);
  }
  return Array.from(map.entries()).map(([category, savings]) => ({ category, savings }));
}

export function buildOverviewMetrics(input: {
  resources: ResourceItem[];
  waste: { prediction_label: string | null; waste_score: number | null }[];
  risk: RiskAssessmentItem[];
  audit: AuditResultItem[];
  approvals: ApprovalItem[];
  executions: ExecutionItem[];
}) {
  const auditSummary = computeAuditSummary(input.audit);
  const riskStats = computeRiskStats(input.risk);
  const approvalStats = computeApprovalStats(input.approvals);
  const zombies = input.waste.filter(
    (item) => item.prediction_label === "anomaly" || (item.waste_score ?? 0) >= 85
  ).length;

  const labelCounts = new Map<string, number>();
  for (const resource of input.resources) {
    labelCounts.set(resource.resource_label, (labelCounts.get(resource.resource_label) ?? 0) + 1);
  }

  const resourceCategories = Array.from(labelCounts.entries()).map(([name, value], index) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
    color: ["#3FB950", "#F85149", "#58A6FF", "#7745FF", "#F0B429"][index % 5],
  }));

  const riskDistribution = [
    { level: "Low", count: riskStats.low, fill: "#3FB950" },
    { level: "Medium", count: riskStats.medium, fill: "#F0B429" },
    { level: "High", count: riskStats.high, fill: "#F85149" },
  ];

  const typeSpend = new Map<string, { cost: number; waste: number }>();
  for (const item of input.audit) {
    const current = typeSpend.get(item.resource_type) ?? { cost: 0, waste: 0 };
    current.cost += item.monthly_cost;
    current.waste += item.potential_monthly_savings;
    typeSpend.set(item.resource_type, current);
  }

  const costBreakdownTremor = Array.from(typeSpend.entries()).map(([category, values]) => ({
    category,
    "Total Cost": Math.round(values.cost),
    "Identified Waste": Math.round(values.waste),
  }));

  const wasteTrend = buildWasteTrend(input.audit);

  const recentActivity = buildRecentActivity(input.approvals, input.executions, input.risk);

  return {
    kpis: {
      monthlyWaste: Math.round(auditSummary.potentialMonthlySavings),
      annualSavings: Math.round(auditSummary.potentialAnnualSavings),
      resourcesScanned: input.resources.length,
      highRiskResources: riskStats.high,
      totalMonthlySpend: Math.round(auditSummary.totalMonthlyCost),
      zombieResources: zombies,
      pendingApprovals: approvalStats.pending,
    },
    riskDistribution,
    riskDistributionTremor: riskDistribution.map((item) => ({
      name: item.level,
      count: item.count,
    })),
    resourceCategories,
    costBreakdownTremor,
    wasteTrend,
    wasteTrendTremor: wasteTrend.map((item) => ({
      week: item.week,
      Waste: item.waste,
      Recovered: item.recovered,
    })),
    recentActivity,
  };
}

function buildWasteTrend(audit: AuditResultItem[]) {
  const totalWaste = audit.reduce((sum, item) => sum + item.potential_monthly_savings, 0);
  const totalRecovered = audit
    .filter((item) => item.recommendation === "Safe To Remediate")
    .reduce((sum, item) => sum + item.potential_monthly_savings, 0);

  return Array.from({ length: 8 }, (_, index) => {
    const factor = (index + 1) / 8;
    return {
      week: `W${index + 1}`,
      waste: Math.round(totalWaste * factor),
      recovered: Math.round(totalRecovered * factor * 0.85),
      baseline: Math.round(totalWaste * 0.95),
    };
  });
}

function buildRecentActivity(
  approvals: ApprovalItem[],
  executions: ExecutionItem[],
  risk: RiskAssessmentItem[]
) {
  const events: {
    id: string;
    message: string;
    time: string;
    status: "success" | "warning" | "error" | "info";
  }[] = [];

  for (const execution of executions.slice(0, 3)) {
    events.push({
      id: execution.execution_id,
      message: `${execution.status} ${execution.action} on ${execution.resource_id}`,
      time: formatRelativeTime(execution.timestamp),
      status: execution.status === "success" ? "success" : "warning",
    });
  }

  for (const approval of approvals.filter((item) => item.status !== "pending").slice(0, 3)) {
    events.push({
      id: approval.approval_id,
      message: `${approval.status} ${approval.action} — ${approval.resource_id}`,
      time: formatRelativeTime(approval.updated_at),
      status: approval.status === "rejected" ? "error" : "success",
    });
  }

  const topRisk = [...risk].sort((a, b) => b.risk_score - a.risk_score)[0];
  if (topRisk) {
    events.push({
      id: topRisk.resource_id,
      message: `High risk flagged: ${topRisk.resource_id} (${topRisk.environment})`,
      time: "recent",
      status: "warning",
    });
  }

  return events.slice(0, 6);
}

function formatRelativeTime(timestamp: string): string {
  const diffMs = Date.now() - new Date(timestamp).getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `${Math.max(minutes, 1)}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function riskBadgeVariant(level: string): "destructive" | "warning" | "success" {
  if (level === "high") return "destructive";
  if (level === "medium") return "warning";
  return "success";
}

export function formatRiskLevel(level: string): string {
  return level.charAt(0).toUpperCase() + level.slice(1);
}

export function statusBadgeVariant(
  status: string
): "warning" | "success" | "destructive" | "default" | "secondary" {
  if (status === "pending") return "warning";
  if (status === "approved" || status === "executed" || status === "success") return "success";
  if (status === "rejected" || status === "failed") return "destructive";
  return "secondary";
}

export function formatAction(action: string): string {
  return action.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function formatStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function historyStatusVariant(
  status: string
): "warning" | "success" | "destructive" | "secondary" {
  const variant = statusBadgeVariant(status);
  if (variant === "default") return "secondary";
  return variant;
}
