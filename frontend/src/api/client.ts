import axios, { type AxiosResponse, type InternalAxiosRequestConfig } from "axios";

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "");
const isDev = import.meta.env.DEV;

/** A production build must receive its backend URL via VITE_API_BASE_URL. */
export const API_BASE_URL = rawBaseUrl ?? "/api";
if (!rawBaseUrl && !isDev) {
  console.error("VITE_API_BASE_URL is not configured; production API calls will use /api and require a same-origin proxy.");
}

let csrfToken: string | null = null;

export function clearCsrfToken() {
  csrfToken = null;
}

export function setCsrfToken(value: string) {
  csrfToken = value;
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

apiClient.interceptors.request.use(async (config) => {
  if (["post", "put", "patch", "delete"].includes((config.method ?? "get").toLowerCase())) {
    if (!csrfToken) {
      const response = await apiClient.get<{ csrf_token: string }>("/auth/csrf");
      csrfToken = response.data.csrf_token;
    }
    config.headers.set("X-CSRF-Token", csrfToken);
  }
  return config;
});

function logRequest(config: InternalAxiosRequestConfig) {
  if (!import.meta.env.DEV) return config;
  const method = config.method?.toUpperCase() ?? "GET";
  const url = `${config.baseURL ?? ""}${config.url ?? ""}`;
  console.debug(`[API] → ${method} ${url}`);
  return config;
}

function logResponse(response: AxiosResponse) {
  if (!import.meta.env.DEV) return response;
  const method = response.config.method?.toUpperCase() ?? "GET";
  const url = `${response.config.baseURL ?? ""}${response.config.url ?? ""}`;
  console.debug(`[API] ← ${response.status} ${method} ${url}`);
  return response;
}

function logError(error: unknown) {
  if (!import.meta.env.DEV) return;
  if (axios.isAxiosError(error)) {
    const method = error.config?.method?.toUpperCase() ?? "GET";
    const url = `${error.config?.baseURL ?? ""}${error.config?.url ?? ""}`;
    console.debug(`[API] ✕ ${error.response?.status ?? "ERR"} ${method} ${url}`, error.message);
  }
}

apiClient.interceptors.request.use(logRequest);
apiClient.interceptors.response.use(logResponse, (error) => {
  logError(error);

  if (axios.isAxiosError(error)) {
    const url = error.config?.url ?? "";
    const isCredentialSubmission = /\/auth\/(login|register)$/.test(url);
    if (error.response?.status === 401 && !isCredentialSubmission && typeof window !== "undefined") {
      window.dispatchEvent(new Event("auth:expired"));
    }
    const detail =
      typeof error.response?.data?.detail === "string"
        ? error.response.data.detail
        : error.message;
    return Promise.reject(new Error(detail || "Request failed"));
  }

  return Promise.reject(error instanceof Error ? error : new Error("Request failed"));
});
