/** API response types aligned with FastAPI backend schemas. */

export interface PaginatedResponse<T> {
  count: number;
  items: T[];
}

export interface HealthResponse {
  status: string;
}

export interface ResourceItem {
  resource_id: string;
  avg_cpu: number;
  avg_network_in: number;
  avg_network_out: number;
  monthly_cost: number;
  resource_label: string;
}

export interface WasteScoreItem {
  resource_id: string;
  waste_score: number | null;
  waste_probability: string | null;
  utilization_category: string | null;
  forecast_avg_cpu: number | null;
  anomaly_score: number | null;
  prediction_label: string | null;
  monthly_cost: number | null;
}

export interface RiskAssessmentItem {
  resource_id: string;
  waste_score: number;
  monthly_cost: number;
  waste_probability: string;
  environment: string;
  business_critical: boolean;
  attached_to_load_balancer: boolean;
  member_of_autoscaling_group: boolean;
  owner_exists: boolean;
  recent_activity_days: number;
  risk_score: number;
  risk_level: string;
  risk_explanation: string;
  recommendation: string;
}

export interface AuditResultItem {
  resource_id: string;
  resource_type: string;
  monthly_cost: number;
  annual_cost: number;
  waste_score: number;
  risk_level: string;
  priority_score: number;
  priority_category: string;
  potential_monthly_savings: number;
  potential_annual_savings: number;
  recommendation: string;
}

export interface ExecutiveReport {
  executive_summary: string;
  key_findings: string[];
  top_cost_drivers: string[];
  recommended_actions: string[];
  risk_considerations: string[];
  estimated_savings: {
    monthly_usd: number;
    annual_usd: number;
  };
  source: string;
}

export interface RemediationPlanItem {
  resource_id: string;
  action: string;
  risk_level: string;
  estimated_savings: number;
  execution_steps: string;
  business_justification: string;
  resource_type?: string | null;
  waste_score?: number | null;
  recommendation?: string | null;
  technical_justification?: string | null;
  expected_outcome?: string | null;
  risk_explanation?: string | null;
  risk_score?: number | null;
  monthly_cost?: number | null;
  annual_cost?: number | null;
}

export interface ApprovalItem {
  approval_id: string;
  resource_id: string;
  action: string;
  risk_level: string;
  estimated_savings: number;
  business_justification: string;
  execution_steps: string[];
  status: string;
  created_at: string;
  updated_at: string;
  reviewed_by: string | null;
  review_notes: string | null;
}

export interface ApprovalActionRequest {
  reviewer?: string;
  notes?: string | null;
}

export interface ExecutionItem {
  execution_id: string;
  approval_id: string;
  resource_id: string;
  action: string;
  status: string;
  timestamp: string;
  estimated_savings?: number;
  mode?: string;
  execution_steps?: string[];
  rollback_steps?: string[];
  risk_level?: string | null;
  risk_score?: number | null;
  risk_explanation?: string | null;
  logs?: string[];
  error_message?: string | null;
}

export interface EnrichedResource extends ResourceItem {
  waste_score: number | null;
  waste_probability: string | null;
  risk_score: number | null;
  risk_level: string | null;
  environment: string | null;
}

export interface AnomalyStats {
  total: number;
  anomalies: number;
  normal: number;
  contamination_pct: number;
}

export interface AnomalyHistogramBin {
  bin: string;
  count: number;
}

export interface AnomalyPrediction {
  resource_id: string;
  avg_cpu: number;
  avg_network_in: number;
  avg_network_out: number;
  monthly_cost: number;
  resource_label: string;
  prediction: number;
  anomaly_score: number;
  prediction_label: string;
}

export interface AnomalyDashboard {
  stats: AnomalyStats;
  histogram: AnomalyHistogramBin[];
  suspicious: AnomalyPrediction[];
  scatter: AnomalyPrediction[];
}

export type WasteProbability = "high" | "medium" | "low";
export type UtilizationCategory = "idle" | "low_usage" | "healthy" | "high_usage";

export interface ForecastResource {
  resource_id: string;
  resource_type: string;
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

export interface ForecastDashboard {
  meta: { history_days: number; forecast_days: number; generated_from: string };
  stats: ForecastStats;
  waste_distribution: WasteDistributionBin[];
  resources: ForecastResource[];
  chart_data: Record<string, ResourceChartSeries>;
}

export interface ExecutionTriggerResponse {
  execution_id: string;
  approval_id: string;
  resource_id: string;
  action: string;
  status: string;
  mode: string;
  log_path: string | null;
  message: string;
}

export interface ScanStartResponse {
  scan_id: string;
  status: string;
  message: string;
}

export interface ScanStepProgress {
  name: string;
  status: string;
}

export interface ScanStatusResponse {
  scan_id?: string | null;
  status: string;
  progress: number;
  current_step?: string | null;
  steps?: ScanStepProgress[];
  message?: string | null;
  error?: string | null;
}
