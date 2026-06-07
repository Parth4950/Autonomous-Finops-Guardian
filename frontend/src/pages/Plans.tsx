import { useMemo, useState } from "react";
import { ActionDistributionChart } from "@/components/plans/ActionDistributionChart";
import { PlanDetailDrawer } from "@/components/plans/PlanDetailDrawer";
import { PlansKpiCards } from "@/components/plans/PlansKpiCards";
import { RemediationPlansTable } from "@/components/plans/RemediationPlansTable";
import { ChartPanel } from "@/components/dashboard/OverviewWidgets";
import { PageHeader } from "@/components/shared/PageHeader";
import { QueryState } from "@/components/shared/QueryState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuditQuery, usePlansQuery, useRiskQuery } from "@/hooks/useApiQueries";
import {
  buildActionDistribution,
  computePlanSummary,
  enrichPlans,
  type EnrichedPlan,
} from "@/lib/plan-transforms";
import { GitBranch, Workflow } from "lucide-react";

const WORKFLOW_STEPS = [
  { label: "Audit", detail: "Financial waste identified" },
  { label: "Risk", detail: "Safety gates applied" },
  { label: "Plan", detail: "Deterministic action selected" },
  { label: "Justify", detail: "Gemini explains action" },
  { label: "Approve", detail: "Human governance" },
] as const;

export default function PlansPage() {
  const { data: plans = [], isLoading, isError, error, refetch } = usePlansQuery();
  const { data: audit = [] } = useAuditQuery();
  const { data: risk = [] } = useRiskQuery();

  const [selectedPlan, setSelectedPlan] = useState<EnrichedPlan | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const enriched = useMemo(() => enrichPlans(plans, audit, risk), [plans, audit, risk]);
  const summary = useMemo(() => computePlanSummary(enriched), [enriched]);
  const actionDistribution = useMemo(() => buildActionDistribution(enriched), [enriched]);

  function handleOpenDetail(plan: EnrichedPlan) {
    setSelectedPlan(plan);
    setDrawerOpen(true);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Remediation Plans"
        description="AI-generated remediation plans — deterministic actions with Gemini justifications"
      >
        <div className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs">
          <Workflow className="h-3.5 w-3.5 text-primary" />
          <span className="text-muted-foreground">Planner Agent</span>
          <span className="text-emerald-400">{enriched.length} plans</span>
        </div>
      </PageHeader>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card/40 px-4 py-3">
        <GitBranch className="h-4 w-4 text-muted-foreground" />
        {WORKFLOW_STEPS.map((step, index) => (
          <div key={step.label} className="flex items-center gap-2">
            <div className="rounded-md border border-border bg-secondary/50 px-2.5 py-1">
              <p className="text-xs font-semibold">{step.label}</p>
              <p className="text-[10px] text-muted-foreground">{step.detail}</p>
            </div>
            {index < WORKFLOW_STEPS.length - 1 && (
              <span className="text-muted-foreground">→</span>
            )}
          </div>
        ))}
      </div>

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={!isLoading && enriched.length === 0}
        loadingMessage="Loading remediation plans..."
        emptyMessage="No remediation plans found. Run agents/planner/planner.py first."
      >
        <>
          <PlansKpiCards
            plannedSavings={summary.plannedSavings}
            terminateCount={summary.terminateCount}
            resizeCount={summary.resizeCount}
            manualReviewCount={summary.manualReviewCount}
          />

          <ChartPanel
            title="Action Distribution"
            subtitle="Remediation actions across all planned resources"
          >
            {actionDistribution.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                No action distribution available.
              </p>
            ) : (
              <ActionDistributionChart data={actionDistribution} />
            )}
          </ChartPanel>

          <Card>
            <CardHeader>
              <CardTitle>Remediation Plans</CardTitle>
              <p className="text-xs text-muted-foreground">
                Click a row to expand justifications and execution steps · open drawer for full workflow
              </p>
            </CardHeader>
            <CardContent>
              <RemediationPlansTable data={enriched} onOpenDetail={handleOpenDetail} />
            </CardContent>
          </Card>
        </>
      </QueryState>

      <PlanDetailDrawer
        plan={selectedPlan}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
