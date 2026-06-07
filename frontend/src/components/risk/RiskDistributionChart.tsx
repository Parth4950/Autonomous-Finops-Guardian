import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface RiskDistributionChartProps {
  distribution: { level: "low" | "medium" | "high"; count: number }[];
}

const THEME = {
  grid: "#2F3339",
  axis: "#8B919A",
  tooltip: { bg: "#1A1D21", border: "#2F3339" },
  colors: {
    low: "#3FB950",
    medium: "#D29922",
    high: "#F85149",
  },
};

const LABELS: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

export function RiskDistributionChart({ distribution }: RiskDistributionChartProps) {
  const chartData = distribution.map((bin) => ({
    ...bin,
    label: LABELS[bin.level] ?? bin.level,
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="label"
          stroke={THEME.axis}
          fontSize={12}
          tickLine={false}
          axisLine={false}
        />
        <YAxis stroke={THEME.axis} fontSize={11} tickLine={false} axisLine={false} />
        <Tooltip
          contentStyle={{
            background: THEME.tooltip.bg,
            border: `1px solid ${THEME.tooltip.border}`,
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value: number) => [`${value} resources`, "Count"]}
          labelFormatter={(label) => `Risk level: ${label}`}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {chartData.map((entry) => (
            <Cell
              key={entry.level}
              fill={THEME.colors[entry.level as keyof typeof THEME.colors]}
              fillOpacity={0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
