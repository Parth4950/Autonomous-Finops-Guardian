import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const THEME = {
  grid: "#2F3339",
  axis: "#8B919A",
  tooltip: { bg: "#1A1D21", border: "#2F3339" },
  bar: "#58A6FF",
};

interface PriorityScoreChartProps {
  data: { bin: string; count: number }[];
}

export function PriorityScoreChart({ data }: PriorityScoreChartProps) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="bin"
          stroke={THEME.axis}
          fontSize={11}
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
          labelFormatter={(label) => `Priority score: ${label}`}
        />
        <Bar dataKey="count" fill={THEME.bar} radius={[4, 4, 0, 0]} fillOpacity={0.85} />
      </BarChart>
    </ResponsiveContainer>
  );
}
