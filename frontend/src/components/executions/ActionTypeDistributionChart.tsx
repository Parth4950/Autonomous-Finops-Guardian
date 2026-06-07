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

const THEME = {
  grid: "#2F3339",
  axis: "#8B919A",
  tooltip: { bg: "#1A1D21", border: "#2F3339" },
};

interface ActionTypeDistributionChartProps {
  data: { action: string; label: string; count: number; fill: string }[];
}

export function ActionTypeDistributionChart({ data }: ActionTypeDistributionChartProps) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="label"
          stroke={THEME.axis}
          fontSize={11}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke={THEME.axis}
          fontSize={11}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{
            background: THEME.tooltip.bg,
            border: `1px solid ${THEME.tooltip.border}`,
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.action} fill={entry.fill} fillOpacity={0.9} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
