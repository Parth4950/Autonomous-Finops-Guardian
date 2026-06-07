import forecastData from "@/data/forecast-predictions.json";

export type WasteProbability = "high" | "medium" | "low";
export type UtilizationCategory = "idle" | "low_usage" | "healthy" | "high_usage";
export type ResourceType = "healthy" | "zombie" | "seasonal" | "unknown";

export interface ForecastResource {
  resource_id: string;
  resource_type: ResourceType;
  historical_avg_cpu: number;
  forecast_avg_cpu: number;
  forecast_min_cpu: number;
  forecast_max_cpu: number;
  utilization_category: UtilizationCategory;
  waste_probability: WasteProbability;
}

export interface ForecastStats {
  total: number;
  waste_high: number;
  waste_medium: number;
  waste_low: number;
  idle: number;
  low_usage: number;
  healthy: number;
  high_usage: number;
}

export interface WasteDistributionBin {
  category: WasteProbability;
  count: number;
}

export interface HistoricalPoint {
  date: string;
  cpu: number;
}

export interface ForecastPoint {
  date: string;
  cpu: number;
  lower: number;
  upper: number;
}

export interface ResourceChartSeries {
  forecast_start: string;
  historical: HistoricalPoint[];
  forecast: ForecastPoint[];
}

export interface ForecastChartPoint {
  date: string;
  actual: number | null;
  forecast: number | null;
  lower: number | null;
  upper: number | null;
  band: number | null;
}

interface ForecastDataFile {
  meta: { history_days: number; forecast_days: number; generated_from: string };
  stats: ForecastStats;
  waste_distribution: WasteDistributionBin[];
  resources: ForecastResource[];
  chart_data: Record<string, ResourceChartSeries>;
}

const data = forecastData as ForecastDataFile;

export const forecastMeta = data.meta;
export const forecastStats: ForecastStats = data.stats;
export const wasteDistribution: WasteDistributionBin[] = data.waste_distribution;
export const forecastResources: ForecastResource[] = data.resources;
export const forecastChartData = data.chart_data;

export function getResourceChartSeries(resourceId: string): ForecastChartPoint[] {
  const series = forecastChartData[resourceId];
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
