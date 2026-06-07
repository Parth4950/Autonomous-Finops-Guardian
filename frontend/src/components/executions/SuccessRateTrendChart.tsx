import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const THEME = {
  grid: "#2F3339",
  axis: "#8B919A",
  tooltip: { bg: "#1A1D21", border: "#2F3339" },
};

interface SuccessRateTrendChartProps {
  data: { label: string; successRate: number; status: string }[];
}

export function SuccessRateTrendChart({ data }: SuccessRateTrendChartProps) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="label"
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
          domain={[0, 100]}
          tickFormatter={(v) => `${v}%`}
        />
        <Tooltip
          contentStyle={{
            background: THEME.tooltip.bg,
            border: `1px solid ${THEME.tooltip.border}`,
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value: number) => [`${value}%`, "Success rate"]}
        />
        <Line
          type="monotone"
          dataKey="successRate"
          stroke="#3FB950"
          strokeWidth={2}
          dot={{ r: 3, fill: "#3FB950" }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
