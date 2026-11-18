import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { fetchScanStatus, startCloudScan, type StartScanOptions } from "@/api/scan";
import type { ScanMode } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/ui/toast";
import { queryKeys } from "@/hooks/queryKeys";
import { loadNotificationPreferences } from "@/lib/preferences";

const REFRESH_KEYS = [
  queryKeys.resources,
  queryKeys.waste,
  queryKeys.risk,
  queryKeys.audit,
  queryKeys.auditReport,
  queryKeys.plans,
  queryKeys.approvals,
  queryKeys.executions,
  queryKeys.enrichedResources,
  queryKeys.overview,
  queryKeys.anomalies,
  queryKeys.forecast,
  queryKeys.scanSource,
] as const;

export function useCloudScan() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { user } = useAuth();
  const previousStatusRef = useRef<string | undefined>(undefined);
  const startRequestRef = useRef(false);

  const statusQuery = useQuery({
    queryKey: queryKeys.scanStatus,
    queryFn: fetchScanStatus,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 1000 : false),
    staleTime: 0,
  });

  const status = statusQuery.data?.status ?? "idle";
  const isScanning = status === "running";

  const startMutation = useMutation({
    mutationFn: (options: ScanMode | StartScanOptions) => startCloudScan(options),
    onSuccess: (_data, options) => {
      const mode = typeof options === "string" ? options : (options.mode ?? "synthetic");
      const label = mode === "aws" ? "Live AWS scan started" : "Synthetic scan started";
      toast.info("Scan Started", `${label} — running FinOps pipeline…`);
      void queryClient.invalidateQueries({ queryKey: queryKeys.scanStatus });
    },
    onError: (error: Error) => {
      if (/already in progress/i.test(error.message)) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.scanStatus });
        return;
      }
      toast.error("Scan Failed", error.message);
    },
    onSettled: () => {
      startRequestRef.current = false;
    },
  });

  useEffect(() => {
    const previousStatus = previousStatusRef.current;
    previousStatusRef.current = status;

    if (previousStatus !== "running") return;

    const prefs = loadNotificationPreferences(user?.id);
    if (status === "completed") {
      if (prefs.scanCompleted) {
        toast.success("Scan Completed", "Dashboard data refreshed from latest pipeline run.");
      }
      void Promise.all(
        REFRESH_KEYS.map((key) => queryClient.invalidateQueries({ queryKey: key }))
      );
    } else if (status === "failed") {
      if (prefs.scanFailed) {
        toast.error("Scan Failed", statusQuery.data?.error ?? "Pipeline execution failed.");
      }
    }
  }, [status, statusQuery.data?.error, queryClient, toast, user?.id]);

  useEffect(() => {
    if (!statusQuery.isError) return;
    toast.error(
      "Scan Failed",
      statusQuery.error?.message ?? "Lost connection while polling scan status."
    );
  }, [statusQuery.isError, statusQuery.error, toast]);

  const activeRequestedMode =
    typeof startMutation.variables === "string"
      ? startMutation.variables
      : startMutation.variables?.mode ?? null;

  return {
    startScan: (options: ScanMode | StartScanOptions) => {
      if (startRequestRef.current || isScanning || startMutation.isPending) return;
      startRequestRef.current = true;
      startMutation.mutate(options);
    },
    isScanning: isScanning || startMutation.isPending,
    progress: startMutation.isPending ? 0 : statusQuery.data?.progress ?? 0,
    currentStep: startMutation.isPending ? undefined : statusQuery.data?.current_step,
    steps: startMutation.isPending ? [] : statusQuery.data?.steps ?? [],
    scanError: statusQuery.data?.error,
    scanStatus: status,
    scanMode: startMutation.isPending
      ? activeRequestedMode ?? statusQuery.data?.scan_mode
      : statusQuery.data?.scan_mode ?? activeRequestedMode,
    isStarting: startMutation.isPending,
  };
}
