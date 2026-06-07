import {
  BarChart as TremorBarChart,
  DonutChart,
  Legend,
} from "@tremor/react";
import { AlertTriangle, Cloud, DollarSign, TrendingDown } from "lucide-react";
import { LiveScanButton } from "@/components/overview/LiveScanButton";
import { ChartLegend, ChartPanel, KpiCard } from "@/components/dashboard/OverviewWidgets";
import { PageHeader, StatusDot } from "@/components/shared/PageHeader";
import { QueryState } from "@/components/shared/QueryState";
import { useOverview } from "@/hooks/useApiQueries";
import { SkeletonKpiGrid } from "@/components/shared/Skeletons";
import { buildOverviewMetrics } from "@/lib/transforms";
import { formatCurrency } from "@/lib/utils";
import { useMemo } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const THEME = {
  grid: "#2F3339",
  axis: "#8B919A",
  tooltip: { bg: "#1A1D21", border: "#2F3339" },
  purple: "#7745FF",
  blue: "#58A6FF",
  green: "#3FB950",
  amber: "#F0B429",
  red: "#F85149",
};

function DarkTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-lg border px-3 py-2 text-xs shadow-xl"
      style={{ background: THEME.tooltip.bg, borderColor: THEME.tooltip.border }}
    >
      <p className="mb-1.5 font-medium text-foreground">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center justify-between gap-6 text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: entry.color }} />
            {entry.name}
          </span>
          <span className="font-mono text-foreground">
            {typeof entry.value === "number" && entry.name.toLowerCase().includes("cost")
              ? formatCurrency(entry.value)
              : entry.value?.toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function OverviewPage() {
  const { data, isLoading, isError, error, refetch } = useOverview();

  const metrics = useMemo(
    () => (data ? buildOverviewMetrics(data) : null),
    [data]
  );

  const totalResources = metrics?.resourceCategories.reduce((sum, item) => sum + item.value, 0) ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="FinOps command center — waste detection, risk posture, and savings pipeline"
      >
        <LiveScanButton />
      </PageHeader>

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={!isLoading && !metrics}
        loadingMessage="Loading dashboard metrics..."
        emptyMessage="No overview data available from the API."
        skeleton={<SkeletonKpiGrid count={6} columns={4} />}
      >
        {metrics && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard
                title="Monthly Waste"
                value={formatCurrency(metrics.kpis.monthlyWaste)}
                delta={0}
                deltaLabel="from audit pipeline"
                icon={<TrendingDown className="h-4 w-4" />}
                accent="red"
              />
              <KpiCard
                title="Annual Savings"
                value={formatCurrency(metrics.kpis.annualSavings)}
                delta={0}
                deltaLabel="recoverable potential"
                icon={<DollarSign className="h-4 w-4" />}
                accent="green"
              />
              <KpiCard
                title="Resources Scanned"
                value={metrics.kpis.resourcesScanned.toLocaleString()}
                delta={0}
                deltaLabel="from /resources"
                icon={<Cloud className="h-4 w-4" />}
                accent="blue"
              />
              <KpiCard
                title="High Risk Resources"
                value={String(metrics.kpis.highRiskResources)}
                delta={0}
                deltaLabel="from /risk"
                icon={<AlertTriangle className="h-4 w-4" />}
                accent="amber"
              />
            </div>

            <div className="grid gap-4 xl:grid-cols-12">
              <ChartPanel
                title="Waste Trend"
                subtitle="Derived savings trajectory from audit results"
                className="xl:col-span-8"
              >
                <ResponsiveContainer width="100%" height={300}>
                  <ComposedChart data={metrics.wasteTrend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="wasteFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={THEME.red} stopOpacity={0.35} />
                        <stop offset="100%" stopColor={THEME.red} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="week" stroke={THEME.axis} fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis
                      stroke={THEME.axis}
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip content={<DarkTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="waste"
                      name="Identified Waste"
                      stroke={THEME.red}
                      fill="url(#wasteFill)"
                      strokeWidth={2}
                    />
                    <Line
                      type="monotone"
                      dataKey="recovered"
                      name="Recovered"
                      stroke={THEME.green}
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="baseline"
                      name="Baseline"
                      stroke={THEME.axis}
                      strokeWidth={1}
                      strokeDasharray="4 4"
                      dot={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
                <ChartLegend
                  items={[
                    { label: "Identified Waste", color: THEME.red },
                    { label: "Recovered Savings", color: THEME.green },
                    { label: "Baseline", color: THEME.axis },
                  ]}
                />
              </ChartPanel>

              <ChartPanel
                title="Risk Distribution"
                subtitle={`${metrics.kpis.highRiskResources + metrics.riskDistribution[0].count + metrics.riskDistribution[1].count} resources assessed`}
                className="xl:col-span-4"
              >
                <DonutChart
                  className="mt-2 h-52"
                  data={metrics.riskDistributionTremor}
                  category="count"
                  index="name"
                  colors={["emerald", "amber", "red"]}
                  valueFormatter={(v) => `${v} resources`}
                  showAnimation
                />
                <Legend
                  className="mt-4"
                  categories={metrics.riskDistribution.map((item) => item.level)}
                  colors={["emerald", "amber", "red"]}
                />
                <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4">
                  {metrics.riskDistribution.map((item) => (
                    <div key={item.level} className="text-center">
                      <p className="text-lg font-semibold tabular-nums" style={{ color: item.fill }}>
                        {item.count}
                      </p>
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{item.level}</p>
                    </div>
                  ))}
                </div>
              </ChartPanel>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <ChartPanel
                title="Cost Breakdown"
                subtitle={`Total monthly spend: ${formatCurrency(metrics.kpis.totalMonthlySpend)}`}
              >
                {metrics.costBreakdownTremor.length === 0 ? (
                  <QueryState isLoading={false} isError={false} isEmpty emptyMessage="No cost breakdown data." />
                ) : (
                  <>
                    <TremorBarChart
                      className="mt-2 h-72"
                      data={metrics.costBreakdownTremor}
                      index="category"
                      categories={["Total Cost", "Identified Waste"]}
                      colors={["blue", "red"]}
                      valueFormatter={(v) => formatCurrency(v)}
                      showAnimation
                      yAxisWidth={56}
                    />
                    <ChartLegend
                      items={[
                        { label: "Total Cost", color: THEME.blue },
                        { label: "Identified Waste", color: THEME.red },
                      ]}
                    />
                  </>
                )}
              </ChartPanel>

              <ChartPanel
                title="Resource Categories"
                subtitle={`${totalResources} resources from /resources`}
              >
                {metrics.resourceCategories.length === 0 ? (
                  <QueryState isLoading={false} isError={false} isEmpty emptyMessage="No resource categories." />
                ) : (
                  <>
                    <div className="grid gap-4 md:grid-cols-2">
                      <ResponsiveContainer width="100%" height={220}>
                        <PieChart>
                          <Pie
                            data={metrics.resourceCategories}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={52}
                            outerRadius={78}
                            paddingAngle={2}
                            stroke="transparent"
                          >
                            {metrics.resourceCategories.map((entry) => (
                              <Cell key={entry.name} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip content={<DarkTooltip />} />
                        </PieChart>
                      </ResponsiveContainer>

                      <div className="flex flex-col justify-center space-y-2">
                        {metrics.resourceCategories.map((cat) => (
                          <div key={cat.name} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: cat.color }} />
                              <span className="text-muted-foreground">{cat.name}</span>
                            </div>
                            <span className="font-mono tabular-nums text-foreground">{cat.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </ChartPanel>
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              <ChartPanel title="Risk Distribution Detail" subtitle="From /risk endpoint" className="lg:col-span-2">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={metrics.riskDistribution} barCategoryGap="20%">
                    <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="level" stroke={THEME.axis} fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis stroke={THEME.axis} fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip content={<DarkTooltip />} />
                    <Bar dataKey="count" name="Resources" radius={[4, 4, 0, 0]}>
                      {metrics.riskDistribution.map((entry) => (
                        <Cell key={entry.level} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartPanel>

              <ChartPanel title="Pipeline Activity" subtitle="From /executions and /approvals">
                {metrics.recentActivity.length === 0 ? (
                  <QueryState isLoading={false} isError={false} isEmpty emptyMessage="No recent activity." />
                ) : (
                  <ul className="space-y-3">
                    {metrics.recentActivity.map((item) => (
                      <li
                        key={item.id}
                        className="flex items-start gap-3 rounded-md border border-border/50 bg-background/40 px-3 py-2.5 text-sm"
                      >
                        <StatusDot status={item.status} />
                        <div className="min-w-0 flex-1">
                          <p className="leading-snug text-foreground">{item.message}</p>
                          <p className="mt-0.5 text-[11px] text-muted-foreground">{item.time}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </ChartPanel>
            </div>
          </>
        )}
      </QueryState>
    </div>
  );
}
