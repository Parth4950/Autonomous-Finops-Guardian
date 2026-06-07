import { useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  actionBadgeVariant,
  formatPlanAction,
  parseExecutionSteps,
  type EnrichedPlan,
} from "@/lib/plan-transforms";
import { formatRiskLevel, riskBadgeVariant } from "@/lib/transforms";
import { formatCurrency } from "@/lib/utils";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Sparkles,
  X,
} from "lucide-react";

interface PlanDetailDrawerProps {
  plan: EnrichedPlan | null;
  open: boolean;
  onClose: () => void;
}

export function PlanDetailDrawer({ plan, open, onClose }: PlanDetailDrawerProps) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open || !plan) return null;

  const steps = parseExecutionSteps(plan.execution_steps);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close drawer"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="plan-drawer-title"
        className="relative flex h-full w-full max-w-xl flex-col border-l border-border bg-[#161A1F] shadow-2xl"
      >
        <div className="flex items-start justify-between border-b border-border px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Action Detail</p>
            <h2 id="plan-drawer-title" className="mt-1 font-mono text-lg font-semibold">
              {plan.resource_id}
            </h2>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant={actionBadgeVariant(plan.action)}>{formatPlanAction(plan.action)}</Badge>
              <Badge variant={riskBadgeVariant(plan.risk_level)} className="capitalize">
                {plan.risk_level} risk
              </Badge>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} className="shrink-0">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          <section className="rounded-lg border border-border bg-card/50 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              Risk Assessment
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <p className="text-xs text-muted-foreground">Risk Level</p>
                <p className="mt-0.5 capitalize font-medium">{formatRiskLevel(plan.risk_level)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Risk Score</p>
                <p className="mt-0.5 font-mono tabular-nums">{plan.risk_score}/100</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Waste Score</p>
                <p className="mt-0.5 font-mono tabular-nums">{plan.waste_score.toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Recommendation</p>
                <p className="mt-0.5 text-sm">{plan.recommendation}</p>
              </div>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              {plan.risk_explanation}
            </p>
          </section>

          <section className="rounded-lg border border-[#7745FF]/30 bg-gradient-to-br from-[#7745FF]/10 to-transparent p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Sparkles className="h-4 w-4 text-[#9B7BFF]" />
              Gemini Justification
            </div>
            <p className="text-sm leading-relaxed text-foreground/90">{plan.business_justification}</p>
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              {plan.technical_justification}
            </p>
          </section>

          <section className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Annual Savings</p>
            <p className="mt-1 text-3xl font-semibold tabular-nums text-emerald-400">
              {formatCurrency(plan.estimated_savings)}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Current spend: {formatCurrency(plan.monthly_cost)}/mo · {formatCurrency(plan.annual_cost)}/yr
            </p>
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <CheckCircle2 className="h-4 w-4 text-blue-400" />
              Execution Workflow
            </div>
            <ol className="space-y-3">
              {steps.map((step, index) => (
                <li key={step} className="flex items-start gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-secondary text-xs font-mono">
                    {index + 1}
                  </span>
                  <div className="flex-1 rounded-md border border-border bg-card/40 px-3 py-2 text-sm">
                    {step}
                  </div>
                  {index < steps.length - 1 && (
                    <ArrowRight className="mt-1.5 hidden h-4 w-4 shrink-0 text-muted-foreground sm:block" />
                  )}
                </li>
              ))}
            </ol>
            <p className="mt-4 text-xs text-muted-foreground">
              Expected outcome: {plan.expected_outcome}
            </p>
          </section>
        </div>

        <div className="border-t border-border px-6 py-4">
          <Button className="w-full" variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </aside>
    </div>
  );
}
