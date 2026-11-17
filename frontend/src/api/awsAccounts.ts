import { apiClient } from "@/api/client";
import type {
  AWSAccount,
  AWSAccountCreateInput,
  AWSAccountUpdateInput,
  PaginatedResponse,
} from "@/api/types";
import { validateObjectResponse, validatePaginatedResponse } from "@/api/validate";

export async function fetchAwsAccounts(): Promise<AWSAccount[]> {
  const { data } = await apiClient.get<PaginatedResponse<AWSAccount>>("/aws/accounts");
  return validatePaginatedResponse<AWSAccount>(data, "aws accounts").items;
}

export async function connectAwsAccount(input: AWSAccountCreateInput): Promise<AWSAccount> {
  const { data } = await apiClient.post<AWSAccount>("/aws/accounts", input);
  return validateObjectResponse<AWSAccount>(data, "aws account connect", [
    "id",
    "display_name",
    "access_key_id_masked",
  ]);
}

export async function verifyAwsAccount(accountId: number, region?: string): Promise<AWSAccount> {
  const { data } = await apiClient.post<AWSAccount>(
    `/aws/accounts/${accountId}/verify`,
    region ? { region } : {}
  );
  return validateObjectResponse<AWSAccount>(data, "aws account verify", [
    "id",
    "verification_status",
  ]);
}

export async function updateAwsAccount(
  accountId: number,
  input: AWSAccountUpdateInput
): Promise<AWSAccount> {
  const { data } = await apiClient.patch<AWSAccount>(`/aws/accounts/${accountId}`, input);
  return validateObjectResponse<AWSAccount>(data, "aws account update", [
    "id",
    "display_name",
    "access_key_id_masked",
  ]);
}

export async function disconnectAwsAccount(accountId: number): Promise<void> {
  await apiClient.delete(`/aws/accounts/${accountId}`);
}
