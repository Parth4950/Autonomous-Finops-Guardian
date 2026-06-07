import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ForecastChart } from "@/components/forecasting/ForecastChart";
import { ForecastComparisonTable } from "@/components/forecasting/ForecastComparisonTable";
import { WasteProbabilityChart } from "@/components/forecasting/WasteProbabilityChart";
import { MetricCard, PageHeader } from "@/components/shared/PageHeader";
import { QueryState } from "@/components/shared/QueryState";
import { SkeletonChart, SkeletonKpiGrid, SkeletonTable } from "@/components/shared/Skeletons";
import { useForecast } from "@/hooks/useApiQueries";

export default function ForecastingPage() {
  const { data, isLoading, isError, error, refetch } = useForecast();

  const avgForecastCpu = data
    ? data.resources.reduce((sum, r) => sum + r.forecast_avg_cpu, 0) / data.resources.length
    : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Forecasting"
        description="Prophet CPU utilization forecasts — 30-day horizon with waste probability classification"
      />

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={!isLoading && !data}
        loadingMessage="Loading forecast data..."
        emptyMessage="No forecast data found. Run ml/forecasting/export_forecast_json.py first."
        skeleton={
          <>
            <SkeletonKpiGrid count={4} />
            <SkeletonChart height={320} />
            <SkeletonTable rows={10} columns={6} />
          </>
        }
      >
        {data && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Resources Forecasted"
                value={data.stats.total}
                subtext={`${data.meta.history_days}-day historical window`}
              />
              <MetricCard
                label="Forecast Average CPU"
                value={`${avgForecastCpu.toFixed(1)}%`}
                subtext={`${data.meta.forecast_days}-day Prophet horizon`}
              />
              <MetricCard
                label="High Waste Probability"
                value={data.stats.waste_high}
                subtext="Persistently idle resources"
              />
              <MetricCard
                label="Healthy Utilization"
                value={data.stats.healthy}
                subtext={`${data.stats.idle} idle · ${data.stats.low_usage} low usage`}
              />
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Historical CPU vs Prophet Forecast</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Interactive actual vs forecast chart with 95% confidence interval — select any resource
                </p>
              </CardHeader>
              <CardContent>
                <ForecastChart
                  chartData={data.chart_data}
                  resources={data.resources}
                />
              </CardContent>
            </Card>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Waste Probability Distribution</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    Classification from historical and forecast CPU utilization trends
                  </p>
                </CardHeader>
                <CardContent>
                  <WasteProbabilityChart data={data.waste_distribution} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Forecast Summary</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    Utilization categories across the {data.meta.forecast_days}-day forecast window
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4">
                    {[
                      { label: "Idle", value: data.stats.idle, color: "text-red-400" },
                      { label: "Low Usage", value: data.stats.low_usage, color: "text-amber-400" },
                      { label: "Healthy", value: data.stats.healthy, color: "text-emerald-400" },
                      { label: "High Usage", value: data.stats.high_usage, color: "text-blue-400" },
                    ].map((item) => (
                      <div key={item.label} className="rounded-lg border border-border p-4">
                        <p className="text-xs text-muted-foreground">{item.label}</p>
                        <p className={`mt-1 text-2xl font-semibold tabular-nums ${item.color}`}>
                          {item.value}
                        </p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Resource Forecast Comparison</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Historical CPU, forecast average, delta, utilization category, and waste probability for
                  all {data.resources.length} resources
                </p>
              </CardHeader>
              <CardContent>
                <ForecastComparisonTable data={data.resources} />
              </CardContent>
            </Card>
          </>
        )}
      </QueryState>
    </div>
  );
}
