import type { WasteDistributionBin } from "@/api/types";
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
  colors: {
    high: "#F85149",
    medium: "#D29922",
    low: "#3FB950",
  },
};

const LABELS: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export function WasteProbabilityChart({ data }: { data: WasteDistributionBin[] }) {
  const chartData = data.map((bin) => ({
    ...bin,
    label: LABELS[bin.category] ?? bin.category,
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
          labelFormatter={(label) => `Waste probability: ${label}`}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {chartData.map((entry) => (
            <Cell
              key={entry.category}
              fill={THEME.colors[entry.category as keyof typeof THEME.colors]}
              fillOpacity={0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
