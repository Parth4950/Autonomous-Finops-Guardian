import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  approveRemediation,
  executeRemediation,
  rejectRemediation,
} from "@/api/approvals";
import { queryKeys } from "@/hooks/queryKeys";

export function useApproveMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      approvalId,
      notes,
      reviewer = "dashboard-reviewer",
    }: {
      approvalId: string;
      notes?: string;
      reviewer?: string;
    }) => approveRemediation(approvalId, { reviewer, notes }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.approvals });
      void queryClient.invalidateQueries({ queryKey: queryKeys.overview });
    },
  });
}

export function useRejectMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      approvalId,
      notes,
      reviewer = "dashboard-reviewer",
    }: {
      approvalId: string;
      notes?: string;
      reviewer?: string;
    }) => rejectRemediation(approvalId, { reviewer, notes }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.approvals });
      void queryClient.invalidateQueries({ queryKey: queryKeys.overview });
    },
  });
}

export function useExecuteMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (approvalId: string) => executeRemediation(approvalId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.executions });
      void queryClient.invalidateQueries({ queryKey: queryKeys.approvals });
      void queryClient.invalidateQueries({ queryKey: queryKeys.overview });
    },
  });
}
