import { apiClient } from "@/api/client";
import type { PaginatedResponse, RiskAssessmentItem } from "@/api/types";
import { validatePaginatedResponse } from "@/api/validate";

export async function fetchRisk(): Promise<RiskAssessmentItem[]> {
  const { data } = await apiClient.get<PaginatedResponse<RiskAssessmentItem>>("/risk");
  return validatePaginatedResponse<RiskAssessmentItem>(data, "risk").items;
}
