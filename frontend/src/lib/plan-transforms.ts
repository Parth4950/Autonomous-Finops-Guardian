import type {
  AuditResultItem,
  RemediationPlanItem,
  RiskAssessmentItem,
} from "@/lib/api/types";
import { formatAction } from "@/lib/transforms";

export type PlanAction =
  | "terminate"
  | "resize"
  | "stop"
  | "snapshot_and_delete"
  | "manual_review"
  | "ignore";

export const PLAN_ACTIONS: PlanAction[] = [
  "terminate",
  "resize",
  "stop",
  "snapshot_and_delete",
  "manual_review",
  "ignore",
];

export const ACTION_LABELS: Record<PlanAction, string> = {
  terminate: "Terminate",
  resize: "Resize",
  stop: "Stop",
  snapshot_and_delete: "Snapshot & Delete",
  manual_review: "Manual Review",
  ignore: "Ignore",
};

export const ACTION_COLORS: Record<PlanAction, string> = {
  terminate: "#F85149",
  resize: "#7745FF",
  stop: "#58A6FF",
  snapshot_and_delete: "#F0B429",
  manual_review: "#E3B341",
  ignore: "#6E7681",
};

export interface EnrichedPlan extends RemediationPlanItem {
  resource_type: string;
  waste_score: number;
  recommendation: string;
  technical_justification: string;
  expected_outcome: string;
  risk_explanation: string;
  risk_score: number;
  monthly_cost: number;
  annual_cost: number;
}

export function parseExecutionSteps(steps: string): string[] {
  return steps
    .split("|")
    .map((step) => step.trim())
    .filter(Boolean);
}

function fallbackTechnical(plan: RemediationPlanItem, resourceType: string, wasteScore: number): string {
  return (
    `The predetermined action '${plan.action}' follows the Planner rules engine based on ` +
    `resource type '${resourceType}', risk level '${plan.risk_level}', and waste score ${wasteScore.toFixed(1)}. ` +
    `Execution will follow the defined step sequence with verification gates.`
  );
}

function fallbackOutcome(plan: RemediationPlanItem, savings: number): string {
  if (plan.action === "ignore") {
    return "No changes will be made; the resource remains under monitoring due to high operational risk or insufficient waste signal.";
  }
  if (plan.action === "manual_review") {
    return "Resource will be queued for stakeholder review before any infrastructure changes are executed.";
  }
  return `Successful execution is expected to eliminate idle spend and recover up to $${savings.toLocaleString()} in annual cloud costs.`;
}

export function enrichPlans(
  plans: RemediationPlanItem[],
  audit: AuditResultItem[],
  risk: RiskAssessmentItem[]
): EnrichedPlan[] {
  const auditMap = new Map(audit.map((item) => [item.resource_id, item]));
  const riskMap = new Map(risk.map((item) => [item.resource_id, item]));

  return plans.map((plan) => {
    const auditRow = auditMap.get(plan.resource_id);
    const riskRow = riskMap.get(plan.resource_id);

    const resourceType = plan.resource_type ?? auditRow?.resource_type ?? "unknown";
    const wasteScore = plan.waste_score ?? auditRow?.waste_score ?? 0;
    const recommendation = plan.recommendation ?? auditRow?.recommendation ?? riskRow?.recommendation ?? "Unknown";
    const riskExplanation = plan.risk_explanation ?? riskRow?.risk_explanation ?? "No risk assessment available.";
    const riskScore = plan.risk_score ?? riskRow?.risk_score ?? 0;
    const monthlyCost = plan.monthly_cost ?? auditRow?.monthly_cost ?? 0;
    const annualCost = plan.annual_cost ?? auditRow?.annual_cost ?? monthlyCost * 12;

    return {
      ...plan,
      resource_type: resourceType,
      waste_score: wasteScore,
      recommendation,
      technical_justification:
        plan.technical_justification ??
        fallbackTechnical(plan, resourceType, wasteScore),
      expected_outcome:
        plan.expected_outcome ?? fallbackOutcome(plan, plan.estimated_savings),
      risk_explanation: riskExplanation,
      risk_score: riskScore,
      monthly_cost: monthlyCost,
      annual_cost: annualCost,
    };
  });
}

export function computePlanSummary(plans: EnrichedPlan[]) {
  return {
    plannedSavings: plans.reduce((sum, plan) => sum + plan.estimated_savings, 0),
    terminateCount: plans.filter((plan) => plan.action === "terminate").length,
    resizeCount: plans.filter((plan) => plan.action === "resize").length,
    manualReviewCount: plans.filter((plan) => plan.action === "manual_review").length,
    stopCount: plans.filter((plan) => plan.action === "stop").length,
    snapshotCount: plans.filter((plan) => plan.action === "snapshot_and_delete").length,
    ignoreCount: plans.filter((plan) => plan.action === "ignore").length,
  };
}

export function buildActionDistribution(plans: EnrichedPlan[]) {
  return PLAN_ACTIONS.map((action) => ({
    action,
    label: ACTION_LABELS[action],
    count: plans.filter((plan) => plan.action === action).length,
    savings: plans
      .filter((plan) => plan.action === action)
      .reduce((sum, plan) => sum + plan.estimated_savings, 0),
    fill: ACTION_COLORS[action],
  })).filter((item) => item.count > 0);
}

export type SavingsSort = "desc" | "asc";

export function filterPlans(
  plans: EnrichedPlan[],
  search: string,
  actionFilter: string,
  riskFilter: string,
  sort: SavingsSort
): EnrichedPlan[] {
  const query = search.trim().toLowerCase();

  const filtered = plans.filter((plan) => {
    const matchesSearch =
      query === "" ||
      plan.resource_id.toLowerCase().includes(query) ||
      plan.resource_type.toLowerCase().includes(query) ||
      plan.action.toLowerCase().includes(query) ||
      plan.recommendation.toLowerCase().includes(query);

    const matchesAction = actionFilter === "all" || plan.action === actionFilter;
    const matchesRisk = riskFilter === "all" || plan.risk_level === riskFilter;

    return matchesSearch && matchesAction && matchesRisk;
  });

  return [...filtered].sort((a, b) =>
    sort === "desc"
      ? b.estimated_savings - a.estimated_savings
      : a.estimated_savings - b.estimated_savings
  );
}

export function actionBadgeVariant(
  action: string
): "destructive" | "warning" | "success" | "secondary" | "default" {
  if (action === "terminate" || action === "snapshot_and_delete") return "destructive";
  if (action === "manual_review") return "warning";
  if (action === "ignore") return "secondary";
  if (action === "resize" || action === "stop") return "default";
  return "secondary";
}

export function formatPlanAction(action: string): string {
  if (action in ACTION_LABELS) {
    return ACTION_LABELS[action as PlanAction];
  }
  return formatAction(action);
}
