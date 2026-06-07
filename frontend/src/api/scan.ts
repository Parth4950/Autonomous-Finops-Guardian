import axios from "axios";
import { API_BASE_URL } from "@/api/client";
import { validateObjectResponse } from "@/api/validate";
import type { ScanStartResponse, ScanStatusResponse } from "@/api/types";

/** Scan polling can outlast default API timeouts while the pipeline runs. */
const scanClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 120_000,
});

scanClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error)) {
      const detail =
        typeof error.response?.data?.detail === "string"
          ? error.response.data.detail
          : error.code === "ECONNABORTED"
            ? "Scan request timed out — the pipeline may still be running on the server."
            : error.message === "Network Error"
              ? "Lost connection to the API. If the backend uses --reload, restart it with --reload-dir backend only."
              : error.message;
      return Promise.reject(new Error(detail || "Request failed"));
    }
    return Promise.reject(error instanceof Error ? error : new Error("Request failed"));
  }
);

export async function startCloudScan(): Promise<ScanStartResponse> {
  const { data } = await scanClient.post<ScanStartResponse>("/scan/start");
  return validateObjectResponse<ScanStartResponse>(data, "scan start", ["scan_id", "status"]);
}

export async function fetchScanStatus(): Promise<ScanStatusResponse> {
  const { data } = await scanClient.get<ScanStatusResponse>("/scan/status");
  return validateObjectResponse<ScanStatusResponse>(data, "scan status", ["status", "progress"]);
}
