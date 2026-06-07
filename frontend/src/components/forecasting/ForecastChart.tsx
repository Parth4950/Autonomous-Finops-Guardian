import { useEffect, useMemo, useState } from "react";
import type { ForecastResource, ResourceChartSeries } from "@/api/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getResourceChartSeries } from "@/lib/forecast-transforms";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
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
  actual: "#58A6FF",
  forecast: "#7745FF",
  band: "#7745FF",
  divider: "#6E7681",
};

function formatDateLabel(value: string) {
  const date = new Date(value);
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ dataKey: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length || !label) return null;

  const actual = payload.find((p) => p.dataKey === "actual")?.value;
  const forecast = payload.find((p) => p.dataKey === "forecast")?.value;
  const lower = payload.find((p) => p.dataKey === "lower")?.value;
  const upper = payload.find((p) => p.dataKey === "upper")?.value;

  return (
    <div
      className="rounded-lg border px-3 py-2 text-xs shadow-xl"
      style={{ background: THEME.tooltip.bg, borderColor: THEME.tooltip.border }}
    >
      <p className="font-medium text-foreground">{formatDateLabel(label)}</p>
      {actual != null && (
        <p style={{ color: THEME.actual }}>Historical CPU: {actual.toFixed(2)}%</p>
      )}
      {forecast != null && (
        <p style={{ color: THEME.forecast }}>Prophet Forecast: {forecast.toFixed(2)}%</p>
      )}
      {lower != null && upper != null && (
        <p className="text-muted-foreground">
          95% interval: {lower.toFixed(1)}% – {upper.toFixed(1)}%
        </p>
      )}
    </div>
  );
}

interface ForecastChartProps {
  chartData: Record<string, ResourceChartSeries>;
  resources: ForecastResource[];
}

export function ForecastChart({ chartData, resources }: ForecastChartProps) {
  const defaultResource = resources[0]?.resource_id ?? "res-healthy-001";
  const [resourceId, setResourceId] = useState(defaultResource);
  const [typeFilter, setTypeFilter] = useState("all");

  const filteredResources = useMemo(() => {
    if (typeFilter === "all") return resources;
    return resources.filter((r) => r.resource_type === typeFilter);
  }, [resources, typeFilter]);

  useEffect(() => {
    if (!filteredResources.some((r) => r.resource_id === resourceId)) {
      setResourceId(filteredResources[0]?.resource_id ?? defaultResource);
    }
  }, [filteredResources, resourceId, defaultResource]);

  const selected = resources.find((r) => r.resource_id === resourceId);
  const series = getResourceChartSeries(chartData, resourceId);
  const forecastStart = chartData[resourceId]?.forecast_start;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="h-9 w-[140px]">
            <SelectValue placeholder="Resource type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="healthy">Healthy</SelectItem>
            <SelectItem value="zombie">Zombie</SelectItem>
            <SelectItem value="seasonal">Seasonal</SelectItem>
          </SelectContent>
        </Select>

        <Select value={resourceId} onValueChange={setResourceId}>
          <SelectTrigger className="h-9 flex-1 sm:max-w-md">
            <SelectValue placeholder="Select resource" />
          </SelectTrigger>
          <SelectContent>
            {filteredResources.map((r) => (
              <SelectItem key={r.resource_id} value={r.resource_id}>
                {r.resource_id} — hist {r.historical_avg_cpu}% → fcst {r.forecast_avg_cpu}%
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {selected && (
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span>
            Historical avg: <strong className="text-foreground">{selected.historical_avg_cpu}%</strong>
          </span>
          <span>
            Forecast avg: <strong className="text-foreground">{selected.forecast_avg_cpu}%</strong>
          </span>
          <span>
            Waste probability:{" "}
            <strong className="capitalize text-foreground">{selected.waste_probability}</strong>
          </span>
        </div>
      )}

      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart data={series} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            stroke={THEME.axis}
            fontSize={10}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatDateLabel}
            minTickGap={28}
          />
          <YAxis
            stroke={THEME.axis}
            fontSize={11}
            tickLine={false}
            axisLine={false}
            domain={[0, 100]}
            unit="%"
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />

          <Area
            type="monotone"
            dataKey="lower"
            stackId="confidence"
            stroke="none"
            fill="transparent"
            legendType="none"
            activeDot={false}
          />
          <Area
            type="monotone"
            dataKey="band"
            stackId="confidence"
            stroke="none"
            fill={THEME.band}
            fillOpacity={0.18}
            name="95% interval"
            activeDot={false}
          />

          {forecastStart && (
            <ReferenceLine
              x={forecastStart}
              stroke={THEME.divider}
              strokeDasharray="4 4"
              label={{
                value: "Forecast start",
                position: "insideTopRight",
                fill: THEME.axis,
                fontSize: 10,
              }}
            />
          )}

          <Line
            type="monotone"
            dataKey="actual"
            stroke={THEME.actual}
            strokeWidth={2}
            dot={false}
            name="Historical CPU"
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="forecast"
            stroke={THEME.forecast}
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            name="Prophet Forecast"
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
