import type { ScanMode } from "@/api/types";
import { useScanSource } from "@/hooks/useApiQueries";
import { useCloudScan } from "@/hooks/useCloudScan";

/** Last completed scan mode from disk, or active scan while running. */
export function useDataScanMode(): ScanMode {
  const { data: scanSource } = useScanSource();
  const { scanMode: activeScanMode, isScanning } = useCloudScan();

  if (isScanning && activeScanMode) {
    return activeScanMode;
  }

  if (scanSource?.mode === "aws" || scanSource?.mode === "synthetic") {
    return scanSource.mode;
  }

  return "synthetic";
}
