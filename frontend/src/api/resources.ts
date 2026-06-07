import { apiClient } from "@/api/client";
import type { PaginatedResponse, ResourceItem } from "@/api/types";
import { validatePaginatedResponse } from "@/api/validate";

export async function fetchResources(): Promise<ResourceItem[]> {
  const { data } = await apiClient.get<PaginatedResponse<ResourceItem>>("/resources");
  return validatePaginatedResponse<ResourceItem>(data, "resources").items;
}
