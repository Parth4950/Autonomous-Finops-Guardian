import { useMemo, useRef, useState } from "react";
import { AnnualSavingsProjectionChart } from "@/components/audit/AnnualSavingsProjectionChart";
import { AuditKpiCards } from "@/components/audit/AuditKpiCards";
import { AuditToolbar } from "@/components/audit/AuditToolbar";
import { ExecutiveSummaryCard } from "@/components/audit/ExecutiveSummaryCard";
import { MonthlyWasteChart } from "@/components/audit/MonthlyWasteChart";
import { PriorityScoreChart } from "@/components/audit/PriorityScoreChart";
import { SavingsByRecommendationChart } from "@/components/audit/SavingsByRecommendationChart";
import { SavingsOpportunitiesTable } from "@/components/audit/SavingsOpportunitiesTable";
import { ChartPanel } from "@/components/dashboard/OverviewWidgets";
import { PageHeader } from "@/components/shared/PageHeader";
import { QueryState } from "@/components/shared/QueryState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuditQuery, useExecutiveReportQuery } from "@/hooks/useApiQueries";
import {
  auditToCsv,
  buildAnnualSavingsProjection,
  buildMonthlyWasteDistribution,
  buildPriorityScoreDistribution,
  buildSavingsByRecommendation,
  downloadCsv,
  getTopSavingsOpportunities,
  projectionMonths,
  type AuditDateRange,
} from "@/lib/audit-transforms";
import { computeAuditSummary } from "@/lib/transforms";
import { formatCurrency } from "@/lib/utils";

export default function AuditPage() {
  const printRef = useRef<HTMLDivElement>(null);
  const [dateRange, setDateRange] = useState<AuditDateRange>("365d");

  const { data = [], isLoading, isError, error, refetch } = useAuditQuery();
  const {
    data: report,
    isLoading: reportLoading,
    isError: reportError,
  } = useExecutiveReportQuery();

  const summary = useMemo(() => computeAuditSummary(data), [data]);
  const topOpportunities = useMemo(() => getTopSavingsOpportunities(data, 20), [data]);
  const months = projectionMonths(dateRange);

  const monthlyWaste = useMemo(() => buildMonthlyWasteDistribution(data), [data]);
  const annualProjection = useMemo(
    () => buildAnnualSavingsProjection(data, months),
    [data, months]
  );
  const priorityDistribution = useMemo(() => buildPriorityScoreDistribution(data), [data]);
  const savingsByRec = useMemo(() => buildSavingsByRecommendation(data), [data]);

  const fallbackSummary = useMemo(() => {
    const underutilized = data.filter((item) => item.potential_monthly_savings > 0).length;
    return `We identified ${underutilized} underutilized resources representing approximately ${formatCurrency(summary.potentialMonthlySavings)} in monthly waste and ${formatCurrency(summary.potentialAnnualSavings)} in annual savings.`;
  }, [data, summary]);

  function handleExportCsv() {
    const csv = auditToCsv(topOpportunities);
    const stamp = new Date().toISOString().slice(0, 10);
    downloadCsv(`finops-audit-top20-${stamp}.csv`, csv);
  }

  function handleExportPdf() {
    window.print();
  }

  const isPageLoading = isLoading || reportLoading;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Reports"
        description="Executive-level cloud waste reporting and savings analysis — Datadog × Grafana analytics"
      />

      <QueryState
        isLoading={isPageLoading}
        isError={isError}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={!isPageLoading && data.length === 0}
        loadingMessage="Loading audit reports..."
        emptyMessage="No audit records found. Run agents/auditor/auditor.py first."
      >
        <div ref={printRef} className="audit-print-root space-y-6">
          <AuditToolbar
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            onExportCsv={handleExportCsv}
            onExportPdf={handleExportPdf}
            recordCount={data.length}
          />

          <AuditKpiCards
            totalMonthlyCost={summary.totalMonthlyCost}
            potentialMonthlySavings={summary.potentialMonthlySavings}
            potentialAnnualSavings={summary.potentialAnnualSavings}
            resourcesAudited={data.length}
          />

          <ExecutiveSummaryCard
            report={reportError ? null : report ?? null}
            fallbackSummary={fallbackSummary}
          />

          <div className="grid gap-4 xl:grid-cols-2">
            <ChartPanel
              title="Monthly Waste Distribution"
              subtitle="Potential monthly waste grouped by severity band"
            >
              <MonthlyWasteChart data={monthlyWaste} />
            </ChartPanel>

            <ChartPanel
              title="Annual Savings Projection"
              subtitle={`Cumulative savings over ${months} month(s) at current run-rate`}
            >
              <AnnualSavingsProjectionChart data={annualProjection} />
            </ChartPanel>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <ChartPanel
              title="Priority Score Distribution"
              subtitle="Auditor priority ranking across all resources"
            >
              <PriorityScoreChart data={priorityDistribution} />
            </ChartPanel>

            <ChartPanel
              title="Savings by Recommendation Category"
              subtitle="Annual and monthly savings by remediation path"
            >
              <SavingsByRecommendationChart data={savingsByRec} />
            </ChartPanel>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Top 20 Savings Opportunities</CardTitle>
              <p className="text-xs text-muted-foreground">
                Highest annual savings potential — sorted by recoverable value
              </p>
            </CardHeader>
            <CardContent>
              <SavingsOpportunitiesTable data={topOpportunities} />
            </CardContent>
          </Card>
        </div>
      </QueryState>
    </div>
  );
}
