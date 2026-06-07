import axios, { type AxiosResponse, type InternalAxiosRequestConfig } from "axios";

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "");
const isDev = import.meta.env.DEV;

/** Use explicit API URL when set; otherwise fall back to Vite dev proxy prefix. */
export const API_BASE_URL = rawBaseUrl ?? (isDev ? "/api" : "http://localhost:8000");

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
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
  if (!import.meta.env.DEV) return Promise.reject(error);
  if (axios.isAxiosError(error)) {
    const method = error.config?.method?.toUpperCase() ?? "GET";
    const url = `${error.config?.baseURL ?? ""}${error.config?.url ?? ""}`;
    console.debug(`[API] ✕ ${error.response?.status ?? "ERR"} ${method} ${url}`, error.message);
  }
  return Promise.reject(error);
}

apiClient.interceptors.request.use(logRequest);
apiClient.interceptors.response.use(logResponse, (error) => {
  logError(error);

  if (axios.isAxiosError(error)) {
    const detail =
      typeof error.response?.data?.detail === "string"
        ? error.response.data.detail
        : error.message;
    return Promise.reject(new Error(detail || "Request failed"));
  }

  return Promise.reject(error instanceof Error ? error : new Error("Request failed"));
});
