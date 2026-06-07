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

interface MonthlyWasteChartProps {
  data: { category: string; waste: number; resources: number; fill: string }[];
}

export function MonthlyWasteChart({ data }: MonthlyWasteChartProps) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="category"
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
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
        />
        <Tooltip
          contentStyle={{
            background: THEME.tooltip.bg,
            border: `1px solid ${THEME.tooltip.border}`,
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value: number, name: string) => {
            if (name === "waste") return [`$${value.toLocaleString()}`, "Monthly waste"];
            return [value, name];
          }}
          labelFormatter={(label) => `Severity: ${label}`}
        />
        <Bar dataKey="waste" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.category} fill={entry.fill} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
