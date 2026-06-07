import { apiClient } from "@/api/client";
import { validateHealthResponse } from "@/api/validate";

export async function fetchHealth(): Promise<{ status: string }> {
  const { data } = await apiClient.get("/health");
  return validateHealthResponse(data);
}
