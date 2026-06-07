import type {
  ResourceChartSeries,
  UtilizationCategory,
  WasteProbability,
} from "@/api/types";

export type ForecastChartPoint = {
  date: string;
  actual: number | null;
  forecast: number | null;
  lower: number | null;
  upper: number | null;
  band: number | null;
};

export function getResourceChartSeries(
  chartData: Record<string, ResourceChartSeries>,
  resourceId: string
): ForecastChartPoint[] {
  const series = chartData[resourceId];
  if (!series) return [];

  const historical = series.historical.map((point) => ({
    date: point.date,
    actual: point.cpu,
    forecast: null as number | null,
    lower: null as number | null,
    upper: null as number | null,
    band: null as number | null,
  }));

  const bridge = historical.length
    ? [
        {
          date: historical[historical.length - 1].date,
          actual: historical[historical.length - 1].actual,
          forecast: historical[historical.length - 1].actual,
          lower: historical[historical.length - 1].actual,
          upper: historical[historical.length - 1].actual,
          band: 0,
        },
      ]
    : [];

  const forecast = series.forecast.map((point) => ({
    date: point.date,
    actual: null as number | null,
    forecast: point.cpu,
    lower: point.lower,
    upper: point.upper,
    band: point.upper - point.lower,
  }));

  return [...historical.slice(0, -1), ...bridge, ...forecast];
}

export function wasteBadgeVariant(
  waste: WasteProbability
): "destructive" | "warning" | "success" {
  if (waste === "high") return "destructive";
  if (waste === "medium") return "warning";
  return "success";
}

export function formatCategory(category: UtilizationCategory): string {
  return category.replace(/_/g, " ");
}

export function cpuDelta(historical: number, forecast: number): number {
  return Number((forecast - historical).toFixed(2));
}

export function formatPrediction(prediction: number): string {
  return prediction === -1 ? "Anomaly (-1)" : "Normal (+1)";
}

export function scoreSeverity(score: number): "critical" | "high" | "medium" | "low" {
  if (score <= -0.05) return "critical";
  if (score <= -0.03) return "high";
  if (score <= -0.01) return "medium";
  return "low";
}

export function formatNetwork(bytes: number): string {
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)}M`;
  if (bytes >= 1_000) return `${(bytes / 1_000).toFixed(1)}K`;
  return bytes.toFixed(0);
}
