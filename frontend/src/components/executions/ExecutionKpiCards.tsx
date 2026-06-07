import { KpiCard } from "@/components/dashboard/OverviewWidgets";
import { formatCurrency } from "@/lib/utils";
import { CheckCircle2, Clock, RotateCcw, XCircle } from "lucide-react";

interface ExecutionKpiCardsProps {
  totalExecutions: number;
  successful: number;
  failed: number;
  rollbacksGenerated: number;
  totalSavings: number;
}

export function ExecutionKpiCards({
  totalExecutions,
  successful,
  failed,
  rollbacksGenerated,
  totalSavings,
}: ExecutionKpiCardsProps) {
  const successRate =
    totalExecutions > 0 ? Math.round((successful / totalExecutions) * 1000) / 10 : 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard
        title="Total Executions"
        value={totalExecutions.toLocaleString()}
        delta={0}
        deltaLabel={`${formatCurrency(totalSavings)} recovered`}
        icon={<Clock className="h-4 w-4" />}
        accent="blue"
      />
      <KpiCard
        title="Successful Actions"
        value={successful.toLocaleString()}
        delta={successRate}
        deltaLabel="success rate"
        icon={<CheckCircle2 className="h-4 w-4" />}
        accent="green"
      />
      <KpiCard
        title="Failed Actions"
        value={failed.toLocaleString()}
        delta={0}
        deltaLabel="requiring investigation"
        icon={<XCircle className="h-4 w-4" />}
        accent="red"
      />
      <KpiCard
        title="Rollbacks Generated"
        value={rollbacksGenerated.toLocaleString()}
        delta={0}
        deltaLabel="recovery plans prepared"
        icon={<RotateCcw className="h-4 w-4" />}
        accent="amber"
      />
    </div>
  );
}
