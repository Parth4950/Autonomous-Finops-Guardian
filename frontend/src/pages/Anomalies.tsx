import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AnomalyScoreHistogram } from "@/components/anomalies/AnomalyScoreHistogram";
import { ResourceScatterPlot } from "@/components/anomalies/ResourceScatterPlot";
import { SuspiciousResourceTable } from "@/components/anomalies/SuspiciousResourceTable";
import { MetricCard, PageHeader } from "@/components/shared/PageHeader";
import { QueryState } from "@/components/shared/QueryState";
import { SkeletonKpiGrid, SkeletonTable } from "@/components/shared/Skeletons";
import { useAnomalies } from "@/hooks/useApiQueries";

export default function AnomaliesPage() {
  const { data, isLoading, isError, error, refetch } = useAnomalies();

  const lowestScore = useMemo(() => {
    const top = data?.suspicious[0];
    return top ? top.anomaly_score.toFixed(4) : "—";
  }, [data]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Anomaly Detection"
        description="Isolation Forest results — unsupervised detection of idle and suspicious cloud resources"
      />

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={!isLoading && !data}
        loadingMessage="Loading anomaly detection results..."
        emptyMessage="No anomaly data found. Run ml/isolation_forest/isolation_detector.py first."
        skeleton={
          <>
            <SkeletonKpiGrid count={4} />
            <SkeletonTable rows={10} columns={5} />
          </>
        }
      >
        {data && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Resources Scored"
                value={data.stats.total}
                subtext="From isolation_detector output"
              />
              <MetricCard
                label="Anomalies Flagged"
                value={data.stats.anomalies}
                subtext={`${data.stats.contamination_pct}% contamination rate`}
              />
              <MetricCard
                label="Normal Classification"
                value={data.stats.normal}
                subtext="prediction = +1"
              />
              <MetricCard
                label="Strongest Anomaly Score"
                value={lowestScore}
                subtext={data.suspicious[0]?.resource_id ?? "Most suspicious resource"}
              />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Anomaly Score Histogram</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    Distribution of decision function scores — lower values indicate stronger anomalies
                  </p>
                </CardHeader>
                <CardContent>
                  <AnomalyScoreHistogram data={data.histogram} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Resource Scatter Plot</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    CPU utilization vs network traffic — anomalies highlighted in red
                  </p>
                </CardHeader>
                <CardContent>
                  <ResourceScatterPlot data={data.scatter} />
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Suspicious Resource Table</CardTitle>
                <p className="text-xs text-muted-foreground">
                  All {data.suspicious.length} resources flagged as anomalies (prediction = -1)
                </p>
              </CardHeader>
              <CardContent>
                <SuspiciousResourceTable data={data.suspicious} />
              </CardContent>
            </Card>
          </>
        )}
      </QueryState>
    </div>
  );
}
