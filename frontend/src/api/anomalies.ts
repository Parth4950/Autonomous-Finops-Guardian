import { apiClient } from "@/api/client";
import type { AnomalyDashboard } from "@/api/types";
import { validateObjectResponse } from "@/api/validate";

export async function fetchAnomalies(): Promise<AnomalyDashboard> {
  const { data } = await apiClient.get<AnomalyDashboard>("/anomalies");
  return validateObjectResponse<AnomalyDashboard>(data, "anomalies", ["stats", "histogram"]);
}
