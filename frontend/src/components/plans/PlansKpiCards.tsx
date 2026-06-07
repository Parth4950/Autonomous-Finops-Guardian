import { KpiCard } from "@/components/dashboard/OverviewWidgets";
import { formatCurrency } from "@/lib/utils";
import { ClipboardList, Scissors, Trash2, UserCheck } from "lucide-react";

interface PlansKpiCardsProps {
  plannedSavings: number;
  terminateCount: number;
  resizeCount: number;
  manualReviewCount: number;
}

export function PlansKpiCards({
  plannedSavings,
  terminateCount,
  resizeCount,
  manualReviewCount,
}: PlansKpiCardsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard
        title="Planned Savings"
        value={formatCurrency(plannedSavings)}
        delta={0}
        deltaLabel="annual recoverable value"
        icon={<ClipboardList className="h-4 w-4" />}
        accent="green"
      />
      <KpiCard
        title="Resources To Terminate"
        value={terminateCount.toLocaleString()}
        delta={0}
        deltaLabel="low-risk zombie instances"
        icon={<Trash2 className="h-4 w-4" />}
        accent="red"
      />
      <KpiCard
        title="Resources To Resize"
        value={resizeCount.toLocaleString()}
        delta={0}
        deltaLabel="rightsizing candidates"
        icon={<Scissors className="h-4 w-4" />}
        accent="purple"
      />
      <KpiCard
        title="Manual Reviews Required"
        value={manualReviewCount.toLocaleString()}
        delta={0}
        deltaLabel="medium-risk escalations"
        icon={<UserCheck className="h-4 w-4" />}
        accent="amber"
      />
    </div>
  );
}
