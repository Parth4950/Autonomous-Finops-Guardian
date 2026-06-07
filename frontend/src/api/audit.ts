import { apiClient } from "@/api/client";
import type { AuditResultItem, ExecutiveReport, PaginatedResponse } from "@/api/types";
import { validateObjectResponse, validatePaginatedResponse } from "@/api/validate";

export async function fetchAudit(): Promise<AuditResultItem[]> {
  const { data } = await apiClient.get<PaginatedResponse<AuditResultItem>>("/audit");
  return validatePaginatedResponse<AuditResultItem>(data, "audit").items;
}

export async function fetchExecutiveReport(): Promise<ExecutiveReport> {
  const { data } = await apiClient.get<ExecutiveReport>("/audit/report");
  return validateObjectResponse<ExecutiveReport>(data, "audit report", [
    "executive_summary",
    "estimated_savings",
  ]);
}
