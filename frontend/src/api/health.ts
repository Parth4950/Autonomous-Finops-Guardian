import { apiClient } from "@/api/client";
import type { HealthResponse } from "@/api/types";
import { validateHealthResponse } from "@/api/validate";

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get("/health");
  return validateHealthResponse(data);
}
