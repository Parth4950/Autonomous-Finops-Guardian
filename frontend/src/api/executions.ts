import { apiClient } from "@/api/client";
import type { ExecutionItem, PaginatedResponse } from "@/api/types";
import { validateObjectResponse, validatePaginatedResponse } from "@/api/validate";

export async function fetchExecutions(): Promise<ExecutionItem[]> {
  const { data } = await apiClient.get<PaginatedResponse<ExecutionItem>>("/executions");
  return validatePaginatedResponse<ExecutionItem>(data, "executions").items;
}

export async function fetchExecution(executionId: string): Promise<ExecutionItem> {
  const { data } = await apiClient.get<ExecutionItem>(`/executions/${executionId}`);
  return validateObjectResponse<ExecutionItem>(data, "execution", [
    "execution_id",
    "resource_id",
    "status",
  ]);
}
