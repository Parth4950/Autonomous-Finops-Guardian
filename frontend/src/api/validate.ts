import type { PaginatedResponse } from "@/api/types";

export class ApiValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiValidationError";
  }
}

export function validatePaginatedResponse<T>(data: unknown, resource: string): PaginatedResponse<T> {
  if (!data || typeof data !== "object") {
    throw new ApiValidationError(`Invalid ${resource} response: expected object`);
  }

  const payload = data as Record<string, unknown>;

  if (!Array.isArray(payload.items)) {
    throw new ApiValidationError(`Invalid ${resource} response: missing items array`);
  }

  if (typeof payload.count !== "number") {
    throw new ApiValidationError(`Invalid ${resource} response: missing count`);
  }

  return payload as unknown as PaginatedResponse<T>;
}

export function validateObjectResponse<T extends object>(
  data: unknown,
  resource: string,
  requiredKeys: (keyof T)[]
): T {
  if (!data || typeof data !== "object") {
    throw new ApiValidationError(`Invalid ${resource} response: expected object`);
  }

  const payload = data as Record<string, unknown>;
  for (const key of requiredKeys) {
    if (!(key as string in payload)) {
      throw new ApiValidationError(`Invalid ${resource} response: missing ${String(key)}`);
    }
  }

  return payload as unknown as T;
}

export function validateHealthResponse(data: unknown): {
  status: string;
  deployment?: "local" | "hosted";
  aws_scan_enabled?: boolean;
  execution_mode?: string;
  revision?: string;
} {
  const payload = validateObjectResponse<{ status: string }>(data, "health", ["status"]);
  const record = data as Record<string, unknown>;
  return {
    status: payload.status,
    deployment:
      record.deployment === "hosted" || record.deployment === "local"
        ? record.deployment
        : undefined,
    aws_scan_enabled:
      typeof record.aws_scan_enabled === "boolean" ? record.aws_scan_enabled : undefined,
    execution_mode:
      typeof record.execution_mode === "string" ? record.execution_mode : undefined,
    revision: typeof record.revision === "string" ? record.revision : undefined,
  };
}
