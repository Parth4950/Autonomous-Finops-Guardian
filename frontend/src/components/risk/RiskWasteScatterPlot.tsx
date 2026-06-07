import { useMemo, useState } from "react";
import type { RiskAssessmentItem } from "@/lib/api/types";
import {
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
  levels: {
    low: "#3FB950",
    medium: "#D29922",
    high: "#F85149",
  },
};

interface RiskWasteScatterPlotProps {
  data: RiskAssessmentItem[];
}

type Point = {
  resource_id: string;
  waste_score: number;
  risk_score: number;
  risk_level: string;
  monthly_cost: number;
  environment: string;
};

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: Point }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;

  return (
    <div
      className="rounded-lg border px-3 py-2 text-xs shadow-xl"
      style={{ background: THEME.tooltip.bg, borderColor: THEME.tooltip.border }}
    >
      <p className="font-mono font-medium text-foreground">{d.resource_id}</p>
      <p className="mt-1 text-muted-foreground">Waste score: {d.waste_score.toFixed(1)}%</p>
      <p className="text-muted-foreground">Risk score: {d.risk_score}</p>
      <p className="capitalize text-muted-foreground">
        Level: <span className="text-foreground">{d.risk_level}</span>
      </p>
      <p className="capitalize text-muted-foreground">Environment: {d.environment}</p>
    </div>
  );
}

export function RiskWasteScatterPlot({ data }: RiskWasteScatterPlotProps) {
  const [envFilter, setEnvFilter] = useState("all");

  const { low, medium, high } = useMemo(() => {
    const points = data.filter((item) => envFilter === "all" || item.environment === envFilter);
    return {
      low: points.filter((item) => item.risk_level === "low"),
      medium: points.filter((item) => item.risk_level === "medium"),
      high: points.filter((item) => item.risk_level === "high"),
    };
  }, [data, envFilter]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {(["all", "production", "staging", "development"] as const).map((env) => (
          <button
            key={env}
            type="button"
            onClick={() => setEnvFilter(env)}
            className={`rounded-md border px-3 py-1 text-xs capitalize ${
              envFilter === env
                ? "border-primary bg-primary/15 text-primary"
                : "border-border text-muted-foreground"
            }`}
          >
            {env === "all" ? "All Environments" : env}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ top: 12, right: 12, bottom: 8, left: 8 }}>
          <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="waste_score"
            name="Waste"
            unit="%"
            stroke={THEME.axis}
            fontSize={11}
            tickLine={false}
            axisLine={false}
            label={{
              value: "Waste Score (%)",
              position: "bottom",
              fill: THEME.axis,
              fontSize: 11,
            }}
          />
          <YAxis
            type="number"
            dataKey="risk_score"
            name="Risk"
            domain={[0, 100]}
            stroke={THEME.axis}
            fontSize={11}
            tickLine={false}
            axisLine={false}
            label={{
              value: "Risk Score",
              angle: -90,
              position: "insideLeft",
              fill: THEME.axis,
              fontSize: 11,
            }}
          />
          <ZAxis type="number" dataKey="monthly_cost" range={[40, 400]} />
          <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: "3 3" }} />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          <Scatter name="Low Risk" data={low} fill={THEME.levels.low} fillOpacity={0.65} />
          <Scatter name="Medium Risk" data={medium} fill={THEME.levels.medium} fillOpacity={0.75} />
          <Scatter name="High Risk" data={high} fill={THEME.levels.high} fillOpacity={0.9} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
