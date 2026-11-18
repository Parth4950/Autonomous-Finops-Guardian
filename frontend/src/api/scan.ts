import { apiClient } from "@/api/client";
import { validateObjectResponse } from "@/api/validate";
import type {
  ScanMode,
  ScanStartRequest,
  ScanStartResponse,
  ScanStatusResponse,
} from "@/api/types";

export interface StartScanOptions {
  mode: ScanMode;
  aws_account_id?: number | null;
  region?: string | null;
}

export async function startCloudScan(
  options: ScanMode | StartScanOptions = "synthetic"
): Promise<ScanStartResponse> {
  const payload: ScanStartRequest =
    typeof options === "string"
      ? { mode: options }
      : {
          mode: options.mode,
          ...(options.aws_account_id != null ? { aws_account_id: options.aws_account_id } : {}),
          ...(options.region ? { region: options.region } : {}),
        };
  const { data } = await apiClient.post<ScanStartResponse>("/scan/start", payload, {
    timeout: 120_000,
  });
  return validateObjectResponse<ScanStartResponse>(data, "scan start", [
    "scan_id",
    "status",
    "scan_mode",
  ]);
}

export async function fetchScanStatus(): Promise<ScanStatusResponse> {
  const { data } = await apiClient.get<ScanStatusResponse>("/scan/status", {
    timeout: 120_000,
  });
  return validateObjectResponse<ScanStatusResponse>(data, "scan status", ["status", "progress"]);
}

export interface ScanSourceResponse {
  mode: "aws" | "synthetic" | "unknown";
  account_id?: string;
  region?: string;
  resource_count?: number;
  generated_at?: string;
}

export async function fetchScanSource(): Promise<ScanSourceResponse> {
  const { data } = await apiClient.get<ScanSourceResponse>("/scan/source");
  return validateObjectResponse<ScanSourceResponse>(data, "scan source", ["mode"]);
}
