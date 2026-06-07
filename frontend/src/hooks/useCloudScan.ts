import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { fetchScanStatus, startCloudScan } from "@/api/scan";
import { useToast } from "@/components/ui/toast";
import { queryKeys } from "@/hooks/queryKeys";

const REFRESH_KEYS = [
  queryKeys.resources,
  queryKeys.waste,
  queryKeys.risk,
  queryKeys.audit,
  queryKeys.auditReport,
  queryKeys.plans,
  queryKeys.enrichedResources,
  queryKeys.overview,
  queryKeys.anomalies,
  queryKeys.forecast,
] as const;

export function useScanStatus(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.scanStatus,
    queryFn: fetchScanStatus,
    enabled,
    refetchInterval: enabled ? 1000 : false,
    retry: 3,
    retryDelay: 1500,
  });
}

export function useCloudScan() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [isPolling, setIsPolling] = useState(false);

  const startMutation = useMutation({
    mutationFn: startCloudScan,
    onSuccess: () => {
      setIsPolling(true);
      toast.info("Scan Started", "Running cloud FinOps pipeline…");
      void queryClient.invalidateQueries({ queryKey: queryKeys.scanStatus });
    },
    onError: (error: Error) => {
      setIsPolling(false);
      toast.error("Scan Failed", error.message);
    },
  });

  const statusQuery = useScanStatus(isPolling || startMutation.isPending);

  useEffect(() => {
    if (!isPolling || !statusQuery.isError) return;

    setIsPolling(false);
    toast.error(
      "Scan Failed",
      statusQuery.error?.message ?? "Lost connection while polling scan status."
    );
  }, [isPolling, statusQuery.isError, statusQuery.error, toast]);

  useEffect(() => {
    if (!isPolling) return;

    const status = statusQuery.data?.status;
    if (!status || status === "running" || status === "idle") return;

    setIsPolling(false);

    if (status === "completed") {
      toast.success("Scan Completed", "Dashboard data refreshed from latest pipeline run.");
      void Promise.all(
        REFRESH_KEYS.map((key) => queryClient.invalidateQueries({ queryKey: key }))
      );
    } else if (status === "failed") {
      toast.error("Scan Failed", statusQuery.data?.error ?? "Pipeline execution failed.");
    }
  }, [isPolling, statusQuery.data, queryClient, toast]);

  const isScanning =
    startMutation.isPending || isPolling || statusQuery.data?.status === "running";

  return {
    startScan: () => startMutation.mutate(),
    isScanning,
    progress: statusQuery.data?.progress ?? (startMutation.isPending ? 5 : 0),
    currentStep: statusQuery.data?.current_step,
    scanStatus: statusQuery.data?.status ?? "idle",
    isStarting: startMutation.isPending,
  };
}
