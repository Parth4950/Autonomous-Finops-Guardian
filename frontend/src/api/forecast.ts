import { apiClient } from "@/api/client";
import type { ForecastDashboard } from "@/api/types";
import { validateObjectResponse } from "@/api/validate";

export async function fetchForecast(): Promise<ForecastDashboard> {
  const { data } = await apiClient.get<ForecastDashboard>("/forecast");
  return validateObjectResponse<ForecastDashboard>(data, "forecast", ["stats", "resources"]);
}
