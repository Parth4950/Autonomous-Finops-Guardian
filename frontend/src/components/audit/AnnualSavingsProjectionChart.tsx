import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const THEME = {
  grid: "#2F3339",
  axis: "#8B919A",
  tooltip: { bg: "#1A1D21", border: "#2F3339" },
  projected: "#7745FF",
  monthly: "#3FB950",
};

interface AnnualSavingsProjectionChartProps {
  data: { month: string; projected: number; monthly: number }[];
}

export function AnnualSavingsProjectionChart({ data }: AnnualSavingsProjectionChartProps) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="projectedFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={THEME.projected} stopOpacity={0.35} />
            <stop offset="100%" stopColor={THEME.projected} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="month"
          stroke={THEME.axis}
          fontSize={10}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke={THEME.axis}
          fontSize={11}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
        />
        <Tooltip
          contentStyle={{
            background: THEME.tooltip.bg,
            border: `1px solid ${THEME.tooltip.border}`,
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value: number, name: string) => [
            `$${value.toLocaleString()}`,
            name === "projected" ? "Cumulative savings" : "Monthly run-rate",
          ]}
        />
        <Area
          type="monotone"
          dataKey="projected"
          stroke={THEME.projected}
          fill="url(#projectedFill)"
          strokeWidth={2}
        />
        <Line
          type="monotone"
          dataKey="monthly"
          stroke={THEME.monthly}
          strokeWidth={2}
          strokeDasharray="4 4"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
