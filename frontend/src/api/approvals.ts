import { apiClient } from "@/api/client";
import type {
  ApprovalActionRequest,
  ApprovalItem,
  ExecutionTriggerResponse,
  PaginatedResponse,
} from "@/api/types";
import { validateObjectResponse, validatePaginatedResponse } from "@/api/validate";

export async function fetchApprovals(): Promise<ApprovalItem[]> {
  const { data } = await apiClient.get<PaginatedResponse<ApprovalItem>>("/approvals");
  return validatePaginatedResponse<ApprovalItem>(data, "approvals").items;
}

export async function approveRemediation(
  approvalId: string,
  payload: ApprovalActionRequest = {}
): Promise<ApprovalItem> {
  const { data } = await apiClient.post<ApprovalItem>(`/approve/${approvalId}`, {
    reviewer: payload.reviewer ?? "dashboard-reviewer",
    notes: payload.notes,
  });
  return validateObjectResponse<ApprovalItem>(data, "approval", ["approval_id", "status"]);
}

export async function rejectRemediation(
  approvalId: string,
  payload: ApprovalActionRequest = {}
): Promise<ApprovalItem> {
  const { data } = await apiClient.post<ApprovalItem>(`/reject/${approvalId}`, {
    reviewer: payload.reviewer ?? "dashboard-reviewer",
    notes: payload.notes,
  });
  return validateObjectResponse<ApprovalItem>(data, "approval", ["approval_id", "status"]);
}

export async function executeRemediation(approvalId: string): Promise<ExecutionTriggerResponse> {
  const { data } = await apiClient.post<ExecutionTriggerResponse>(`/execute/${approvalId}`);
  return validateObjectResponse<ExecutionTriggerResponse>(data, "execution", [
    "execution_id",
    "status",
  ]);
}
