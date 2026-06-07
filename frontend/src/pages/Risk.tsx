import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { HighRiskResourceTable } from "@/components/risk/HighRiskResourceTable";
import { RiskDistributionChart } from "@/components/risk/RiskDistributionChart";
import { RiskWasteScatterPlot } from "@/components/risk/RiskWasteScatterPlot";
import { MetricCard, PageHeader } from "@/components/shared/PageHeader";
import { QueryState } from "@/components/shared/QueryState";
import { useRiskQuery } from "@/hooks/useApiQueries";
import { computeRiskDistribution, computeRiskStats } from "@/lib/transforms";
import { useMemo } from "react";

export default function RiskPage() {
  const { data = [], isLoading, isError, error, refetch } = useRiskQuery();

  const stats = useMemo(() => computeRiskStats(data), [data]);
  const distribution = useMemo(() => computeRiskDistribution(data), [data]);
  const highRiskResources = useMemo(
    () => [...data].filter((item) => item.risk_level === "high").sort((a, b) => b.risk_score - a.risk_score),
    [data]
  );
  const topRisk = highRiskResources[0];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Risk Assessment"
        description="Deterministic rules engine with Gemini-generated explanations — risk scores drive remediation safety"
      />

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={!isLoading && data.length === 0}
        loadingMessage="Loading risk assessments..."
        emptyMessage="No risk assessment records found."
      >
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Resources Assessed"
              value={stats.total}
              subtext={`Avg risk score: ${stats.avg_risk_score}`}
            />
            <MetricCard
              label="High Risk"
              value={stats.high}
              subtext={`${stats.do_not_remediate} do not remediate`}
            />
            <MetricCard
              label="Medium Risk"
              value={stats.medium}
              subtext={`${stats.manual_review} manual review required`}
            />
            <MetricCard
              label="Low Risk"
              value={stats.low}
              subtext={`${stats.safe_to_remediate} safe to remediate`}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Risk Distribution</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Resource counts by deterministic risk level classification
                </p>
              </CardHeader>
              <CardContent>
                <RiskDistributionChart distribution={distribution} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Risk vs Waste Scatter Plot</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Waste score vs risk score — bubble size reflects monthly cost
                </p>
              </CardHeader>
              <CardContent>
                <RiskWasteScatterPlot data={data} />
              </CardContent>
            </Card>
          </div>

          {topRisk && (
            <Card>
              <CardHeader>
                <CardTitle>Highest Risk Resource</CardTitle>
                <p className="text-xs text-muted-foreground">
                  {topRisk.resource_id} — risk score {topRisk.risk_score} ({topRisk.risk_level})
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg border border-border p-4">
                    <p className="text-xs text-muted-foreground">Risk Score</p>
                    <p className="mt-1 text-2xl font-semibold tabular-nums text-red-400">
                      {topRisk.risk_score}
                    </p>
                  </div>
                  <div className="rounded-lg border border-border p-4">
                    <p className="text-xs text-muted-foreground">Risk Level</p>
                    <p className="mt-1 text-2xl font-semibold capitalize">{topRisk.risk_level}</p>
                  </div>
                  <div className="rounded-lg border border-border p-4">
                    <p className="text-xs text-muted-foreground">Recommendation</p>
                    <p className="mt-1 text-sm font-medium">{topRisk.recommendation}</p>
                  </div>
                  <div className="rounded-lg border border-border p-4">
                    <p className="text-xs text-muted-foreground">Waste Score</p>
                    <p className="mt-1 text-2xl font-semibold tabular-nums">{topRisk.waste_score}%</p>
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Gemini Explanation
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-foreground">
                    {topRisk.risk_explanation}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>High-Risk Resources</CardTitle>
              <p className="text-xs text-muted-foreground">
                All {highRiskResources.length} high-risk resources — expand rows for Gemini explanations
              </p>
            </CardHeader>
            <CardContent>
              {highRiskResources.length === 0 ? (
                <QueryState
                  isLoading={false}
                  isError={false}
                  isEmpty
                  emptyMessage="No high-risk resources in the current assessment."
                />
              ) : (
                <HighRiskResourceTable data={highRiskResources} />
              )}
            </CardContent>
          </Card>
        </>
      </QueryState>
    </div>
  );
}
