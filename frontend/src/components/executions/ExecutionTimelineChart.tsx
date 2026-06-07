import {
  Area,
  AreaChart,
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
};

interface ExecutionTimelineChartProps {
  data: { time: string; cumulative: number; status: string; resource_id: string }[];
}

export function ExecutionTimelineChart({ data }: ExecutionTimelineChartProps) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="execTimelineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#7745FF" stopOpacity={0.35} />
            <stop offset="95%" stopColor="#7745FF" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="time"
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
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{
            background: THEME.tooltip.bg,
            border: `1px solid ${THEME.tooltip.border}`,
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value: number) => [value, "Cumulative executions"]}
          labelFormatter={(_label, payload) => {
            const item = payload?.[0]?.payload;
            return item ? `${item.resource_id} · ${item.status}` : "";
          }}
        />
        <Area
          type="stepAfter"
          dataKey="cumulative"
          stroke="#7745FF"
          fill="url(#execTimelineGrad)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
