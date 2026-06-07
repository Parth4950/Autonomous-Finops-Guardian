import anomalyData from "@/data/anomaly-predictions.json";

export interface AnomalyPrediction {
  resource_id: string;
  avg_cpu: number;
  avg_network_in: number;
  avg_network_out: number;
  monthly_cost: number;
  resource_label: string;
  prediction: number;
  anomaly_score: number;
  prediction_label: "anomaly" | "normal";
}

export interface AnomalyHistogramBin {
  bin: string;
  count: number;
}

export interface AnomalyStats {
  total: number;
  anomalies: number;
  normal: number;
  contamination_pct: number;
}

interface AnomalyDataFile {
  stats: AnomalyStats;
  histogram: AnomalyHistogramBin[];
  suspicious: AnomalyPrediction[];
  scatter: AnomalyPrediction[];
}

const data = anomalyData as AnomalyDataFile;

export const anomalyStats: AnomalyStats = data.stats;
export const anomalyHistogram: AnomalyHistogramBin[] = data.histogram;
export const suspiciousResources: AnomalyPrediction[] = data.suspicious;
export const scatterResources: AnomalyPrediction[] = data.scatter;

/** Format Isolation Forest prediction (-1 anomaly, 1 normal). */
export function formatPrediction(prediction: number): string {
  return prediction === -1 ? "Anomaly (-1)" : "Normal (+1)";
}

/** Lower anomaly scores indicate stronger anomaly signal in sklearn IsolationForest. */
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
