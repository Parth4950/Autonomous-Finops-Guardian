import type { AuditResultItem } from "@/lib/api/types";

export type AuditDateRange = "30d" | "90d" | "180d" | "365d";

export const AUDIT_DATE_RANGE_LABELS: Record<AuditDateRange, string> = {
  "30d": "Last 30 days",
  "90d": "Last 90 days",
  "180d": "Last 6 months",
  "365d": "Last 12 months",
};

export function projectionMonths(range: AuditDateRange): number {
  if (range === "30d") return 1;
  if (range === "90d") return 3;
  if (range === "180d") return 6;
  return 12;
}

export function buildMonthlyWasteDistribution(audit: AuditResultItem[]) {
  const bins = [
    { label: "Critical", min: 80, max: 101, color: "#F85149" },
    { label: "High", min: 60, max: 80, color: "#F0B429" },
    { label: "Medium", min: 40, max: 60, color: "#58A6FF" },
    { label: "Low", min: 0, max: 40, color: "#3FB950" },
  ];

  return bins.map((bin) => {
    const items = audit.filter(
      (item) => item.waste_score >= bin.min && item.waste_score < bin.max
    );
    return {
      category: bin.label,
      waste: items.reduce((sum, item) => sum + item.potential_monthly_savings, 0),
      resources: items.length,
      fill: bin.color,
    };
  });
}

export function buildAnnualSavingsProjection(
  audit: AuditResultItem[],
  months: number
) {
  const monthlyTotal = audit.reduce((sum, item) => sum + item.potential_monthly_savings, 0);
  let cumulative = 0;

  return Array.from({ length: months }, (_, index) => {
    cumulative += monthlyTotal;
    const month = new Date();
    month.setMonth(month.getMonth() + index);
    return {
      month: month.toLocaleDateString("en-US", { month: "short", year: "2-digit" }),
      projected: Math.round(cumulative),
      monthly: Math.round(monthlyTotal),
    };
  });
}

export function buildPriorityScoreDistribution(audit: AuditResultItem[]) {
  const bins = [
    { bin: "0–20", min: 0, max: 20 },
    { bin: "20–40", min: 20, max: 40 },
    { bin: "40–60", min: 40, max: 60 },
    { bin: "60–80", min: 60, max: 80 },
    { bin: "80+", min: 80, max: 101 },
  ];

  return bins.map((b) => ({
    bin: b.bin,
    count: audit.filter(
      (item) => item.priority_score >= b.min && item.priority_score < b.max
    ).length,
  }));
}

export function buildSavingsByRecommendation(audit: AuditResultItem[]) {
  const map = new Map<string, { annual: number; monthly: number; count: number }>();

  for (const item of audit) {
    const current = map.get(item.recommendation) ?? { annual: 0, monthly: 0, count: 0 };
    current.annual += item.potential_annual_savings;
    current.monthly += item.potential_monthly_savings;
    current.count += 1;
    map.set(item.recommendation, current);
  }

  return Array.from(map.entries()).map(([category, values]) => ({
    category: category.replace("Safe To Remediate", "Safe To Remediate").replace(
      "Manual Review Required",
      "Manual Review"
    ),
    fullCategory: category,
    annual: Math.round(values.annual),
    monthly: Math.round(values.monthly),
    count: values.count,
  }));
}

export function getTopSavingsOpportunities(audit: AuditResultItem[], limit = 20) {
  return [...audit]
    .sort((a, b) => b.potential_annual_savings - a.potential_annual_savings)
    .slice(0, limit);
}

export function filterAuditResults(
  audit: AuditResultItem[],
  search: string,
  riskFilter: string,
  recommendationFilter: string,
  priorityFilter: string
) {
  return audit.filter((item) => {
    const matchesSearch =
      search === "" ||
      item.resource_id.toLowerCase().includes(search.toLowerCase()) ||
      item.resource_type.toLowerCase().includes(search.toLowerCase());
    const matchesRisk = riskFilter === "all" || item.risk_level === riskFilter;
    const matchesRec =
      recommendationFilter === "all" || item.recommendation === recommendationFilter;
    const matchesPriority =
      priorityFilter === "all" || item.priority_category === priorityFilter;
    return matchesSearch && matchesRisk && matchesRec && matchesPriority;
  });
}

export function auditToCsv(rows: AuditResultItem[]): string {
  const headers = [
    "resource_id",
    "resource_type",
    "monthly_cost",
    "annual_cost",
    "waste_score",
    "risk_level",
    "priority_score",
    "priority_category",
    "potential_monthly_savings",
    "potential_annual_savings",
    "recommendation",
  ];
  const lines = rows.map((row) =>
    headers.map((h) => JSON.stringify(row[h as keyof AuditResultItem] ?? "")).join(",")
  );
  return [headers.join(","), ...lines].join("\n");
}

export function downloadCsv(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function riskBadgeVariant(level: string): "destructive" | "warning" | "success" {
  if (level === "high") return "destructive";
  if (level === "medium") return "warning";
  return "success";
}

export function recommendationBadgeVariant(
  rec: string
): "destructive" | "warning" | "success" | "outline" {
  if (rec === "Do Not Remediate") return "destructive";
  if (rec === "Manual Review Required") return "warning";
  if (rec === "Safe To Remediate") return "success";
  return "outline";
}
