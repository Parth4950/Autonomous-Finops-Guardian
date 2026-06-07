import { apiClient } from "@/api/client";
import type { PaginatedResponse, RemediationPlanItem } from "@/api/types";
import { validatePaginatedResponse } from "@/api/validate";

export async function fetchPlans(): Promise<RemediationPlanItem[]> {
  const { data } = await apiClient.get<PaginatedResponse<RemediationPlanItem>>("/plans");
  return validatePaginatedResponse<RemediationPlanItem>(data, "plans").items;
}
