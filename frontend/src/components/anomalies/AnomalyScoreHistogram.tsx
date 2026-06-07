import type { AnomalyHistogramBin } from "@/api/types";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const THEME = {
  grid: "#2F3339",
  axis: "#8B919A",
  tooltip: { bg: "#1A1D21", border: "#2F3339" },
  anomaly: "#F85149",
  normal: "#7745FF",
};

function barColor(bin: string): string {
  if (bin.startsWith("<") || bin.startsWith("-")) return THEME.anomaly;
  return THEME.normal;
}

interface AnomalyScoreHistogramProps {
  data: AnomalyHistogramBin[];
}

export function AnomalyScoreHistogram({ data }: AnomalyScoreHistogramProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>        <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="bin"
          stroke={THEME.axis}
          fontSize={10}
          tickLine={false}
          axisLine={false}
          angle={-25}
          textAnchor="end"
          height={50}
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
          labelFormatter={(label) => `Score bin: ${label}`}
        />
        <ReferenceLine x="-0.01" stroke={THEME.anomaly} strokeDasharray="4 4" />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.bin} fill={barColor(entry.bin)} fillOpacity={0.85} />
          ))}
        </Bar>      </BarChart>
    </ResponsiveContainer>
  );
}
