import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

const THEME = {
  tooltip: { bg: "#1A1D21", border: "#2F3339" },
};

interface ExecutionStatusChartProps {
  data: { status: string; label: string; count: number; fill: string }[];
}

export function ExecutionStatusChart({ data }: ExecutionStatusChartProps) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={data}
          dataKey="count"
          nameKey="label"
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={95}
          paddingAngle={3}
        >
          {data.map((entry) => (
            <Cell key={entry.status} fill={entry.fill} fillOpacity={0.9} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: THEME.tooltip.bg,
            border: `1px solid ${THEME.tooltip.border}`,
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value: number, _name, props) => [
            value,
            props.payload?.label ?? "Count",
          ]}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
