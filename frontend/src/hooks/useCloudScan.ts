import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { fetchScanStatus, startCloudScan } from "@/api/scan";
import type { ScanMode } from "@/api/types";
import { useToast } from "@/components/ui/toast";
import { queryKeys } from "@/hooks/queryKeys";

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
  const previousStatusRef = useRef<string | undefined>(undefined);

  const statusQuery = useQuery({
    queryKey: queryKeys.scanStatus,
    queryFn: fetchScanStatus,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 1000 : false),
    staleTime: 0,
  });

  const status = statusQuery.data?.status ?? "idle";
  const isScanning = status === "running";

  const startMutation = useMutation({
    mutationFn: (mode: ScanMode) => startCloudScan(mode),
    onSuccess: (_data, mode) => {
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
  });

  useEffect(() => {
    const previousStatus = previousStatusRef.current;
    previousStatusRef.current = status;

    if (previousStatus !== "running") return;

    if (status === "completed") {
      toast.success("Scan Completed", "Dashboard data refreshed from latest pipeline run.");
      void Promise.all(
        REFRESH_KEYS.map((key) => queryClient.invalidateQueries({ queryKey: key }))
      );
    } else if (status === "failed") {
      toast.error("Scan Failed", statusQuery.data?.error ?? "Pipeline execution failed.");
    }
  }, [status, statusQuery.data?.error, queryClient, toast]);

  useEffect(() => {
    if (!statusQuery.isError) return;
    toast.error(
      "Scan Failed",
      statusQuery.error?.message ?? "Lost connection while polling scan status."
    );
  }, [statusQuery.isError, statusQuery.error, toast]);

  return {
    startScan: (mode: ScanMode = "synthetic") => startMutation.mutate(mode),
    isScanning: isScanning || startMutation.isPending,
    progress: statusQuery.data?.progress ?? (startMutation.isPending ? 5 : 0),
    currentStep: statusQuery.data?.current_step,
    scanStatus: status,
    scanMode: statusQuery.data?.scan_mode ?? startMutation.variables ?? null,
    isStarting: startMutation.isPending,
  };
}
