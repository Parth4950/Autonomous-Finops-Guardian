import { KpiCard } from "@/components/dashboard/OverviewWidgets";
import { formatCurrency } from "@/lib/utils";
import { DollarSign, PiggyBank, ScanSearch, TrendingDown } from "lucide-react";

interface AuditKpiCardsProps {
  totalMonthlyCost: number;
  potentialMonthlySavings: number;
  potentialAnnualSavings: number;
  resourcesAudited: number;
}

export function AuditKpiCards({
  totalMonthlyCost,
  potentialMonthlySavings,
  potentialAnnualSavings,
  resourcesAudited,
}: AuditKpiCardsProps) {
  const savingsPct =
    totalMonthlyCost > 0
      ? Math.round((potentialMonthlySavings / totalMonthlyCost) * 1000) / 10
      : 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard
        title="Total Monthly Cloud Cost"
        value={formatCurrency(totalMonthlyCost)}
        delta={0}
        deltaLabel="current audit cycle"
        icon={<DollarSign className="h-4 w-4" />}
        accent="blue"
      />
      <KpiCard
        title="Potential Monthly Savings"
        value={formatCurrency(potentialMonthlySavings)}
        delta={savingsPct}
        deltaLabel="of monthly spend"
        icon={<TrendingDown className="h-4 w-4" />}
        accent="green"
      />
      <KpiCard
        title="Potential Annual Savings"
        value={formatCurrency(potentialAnnualSavings)}
        delta={0}
        deltaLabel="recoverable per year"
        icon={<PiggyBank className="h-4 w-4" />}
        accent="purple"
      />
      <KpiCard
        title="Resources Audited"
        value={resourcesAudited.toLocaleString()}
        delta={0}
        deltaLabel="in scope for this report"
        icon={<ScanSearch className="h-4 w-4" />}
        accent="amber"
      />
    </div>
  );
}
