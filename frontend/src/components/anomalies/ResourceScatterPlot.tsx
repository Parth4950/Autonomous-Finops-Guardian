import { useMemo, useState } from "react";
import type { AnomalyPrediction } from "@/api/types";import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

const THEME = {
  grid: "#2F3339",
  axis: "#8B919A",
  tooltip: { bg: "#1A1D21", border: "#2F3339" },
  anomaly: "#F85149",
  normal: "#58A6FF",
};

type ScatterPoint = {
  resource_id: string;
  avg_cpu: number;
  avg_network_in: number;
  avg_network_out: number;
  anomaly_score: number;
  monthly_cost: number;
  type: string;
};

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ScatterPoint }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div
      className="rounded-lg border px-3 py-2 text-xs shadow-xl"
      style={{ background: THEME.tooltip.bg, borderColor: THEME.tooltip.border }}
    >
      <p className="font-mono font-medium text-foreground">{d.resource_id}</p>
      <p className="mt-1 text-muted-foreground">CPU: {d.avg_cpu.toFixed(2)}%</p>
      <p className="text-muted-foreground">Network In: {d.avg_network_in.toLocaleString()}</p>
      <p className="text-muted-foreground">Network Out: {d.avg_network_out.toLocaleString()}</p>
      <p className="text-red-400">Score: {d.anomaly_score.toFixed(4)}</p>
      <p className="text-muted-foreground capitalize">{d.type}</p>
    </div>
  );
}

export function ResourceScatterPlot({ data }: { data: AnomalyPrediction[] }) {
  const [axis, setAxis] = useState<"network_in" | "network_out">("network_in");

  const { anomalies, normals } = useMemo(() => {
    const points = data.map((r) => ({      resource_id: r.resource_id,
      avg_cpu: r.avg_cpu,
      avg_network_in: r.avg_network_in,
      avg_network_out: r.avg_network_out,
      anomaly_score: r.anomaly_score,
      monthly_cost: r.monthly_cost,
      type: r.prediction_label,
      y: axis === "network_in" ? r.avg_network_in : r.avg_network_out,
    }));
    return {
      anomalies: points.filter((p) => p.type === "anomaly"),
      normals: points.filter((p) => p.type === "normal"),
    };
  }, [axis, data]);
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setAxis("network_in")}
          className={`rounded-md border px-3 py-1 text-xs ${axis === "network_in" ? "border-primary bg-primary/15 text-primary" : "border-border text-muted-foreground"}`}
        >
          CPU vs Network In
        </button>
        <button
          type="button"
          onClick={() => setAxis("network_out")}
          className={`rounded-md border px-3 py-1 text-xs ${axis === "network_out" ? "border-primary bg-primary/15 text-primary" : "border-border text-muted-foreground"}`}
        >
          CPU vs Network Out
        </button>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ top: 12, right: 12, bottom: 8, left: 8 }}>
          <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="avg_cpu"
            name="CPU"
            unit="%"
            stroke={THEME.axis}
            fontSize={11}
            tickLine={false}
            axisLine={false}
            label={{ value: "CPU Utilization (%)", position: "bottom", fill: THEME.axis, fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name={axis === "network_in" ? "Network In" : "Network Out"}
            stroke={THEME.axis}
            fontSize={11}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`}
            label={{
              value: axis === "network_in" ? "Network In (bytes)" : "Network Out (bytes)",
              angle: -90,
              position: "insideLeft",
              fill: THEME.axis,
              fontSize: 11,
            }}
          />
          <ZAxis type="number" dataKey="monthly_cost" range={[40, 400]} />
          <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: "3 3" }} />
          <Legend
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
            formatter={(value) => (
              <span style={{ color: value === "Anomaly" ? THEME.anomaly : THEME.normal }}>{value}</span>
            )}
          />
          <Scatter name="Normal" data={normals} fill={THEME.normal} fillOpacity={0.55} />
          <Scatter name="Anomaly" data={anomalies} fill={THEME.anomaly} fillOpacity={0.9} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
