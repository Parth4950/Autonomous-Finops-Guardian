import { apiClient } from "@/api/client";
import type { PaginatedResponse, WasteScoreItem } from "@/api/types";
import { validatePaginatedResponse } from "@/api/validate";

export async function fetchWaste(): Promise<WasteScoreItem[]> {
  const { data } = await apiClient.get<PaginatedResponse<WasteScoreItem>>("/waste");
  return validatePaginatedResponse<WasteScoreItem>(data, "waste").items;
}
