import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/auth/AuthContext";
import { useAwsAccounts, useHealth, useScanSource } from "@/hooks/useApiQueries";
import { useCloudScan } from "@/hooks/useCloudScan";
import type { ScanMode } from "@/api/types";
import { AWS_REGIONS } from "@/pages/Settings";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  Circle,
  Cloud,
  FlaskConical,
  KeyRound,
  Loader2,
  LogIn,
  Radar,
  XCircle,
} from "lucide-react";
import { useToast } from "@/components/ui/toast";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export function LiveScanButton() {
  const navigate = useNavigate();
  const toast = useToast();
  const { user, isSimulationMode, exitSimulationMode } = useAuth();
  const isGuestSimulation = isSimulationMode && !user;
  const { data: scanSource } = useScanSource();
  const { data: health } = useHealth();
  const { data: awsAccounts } = useAwsAccounts(!isGuestSimulation);
  const awsScanEnabled = (health?.aws_scan_enabled ?? true) && !isGuestSimulation;
  // Keep the user's selected mode separate from deployment capability. If the
  // API temporarily reports AWS scans disabled during startup, the control is
  // forced to synthetic; when health recovers, restore the user's selection.
  const [selectedScanMode, setSelectedScanMode] = useState<ScanMode>("aws");
  const scanMode: ScanMode = awsScanEnabled ? selectedScanMode : "synthetic";
  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [selectedRegion, setSelectedRegion] = useState<string>("us-east-1");
  const {
    startScan,
    isScanning,
    progress,
    currentStep,
    steps,
    scanError,
    scanStatus,
    scanMode: activeScanMode,
  } = useCloudScan();
  const verifiedAccounts = (awsAccounts ?? []).filter(
    (account) => account.verification_status === "verified"
  );
  const selectedAccount = verifiedAccounts.find(
    (account) => String(account.id) === selectedAccountId
  );

  useEffect(() => {
    if (scanSource?.region) {
      setSelectedRegion(scanSource.region);
    }
  }, [scanSource?.region]);

  useEffect(() => {
    if (!awsAccounts) {
      return;
    }
    const stillVerified = verifiedAccounts.some((acc) => String(acc.id) === selectedAccountId);
    if (!stillVerified) {
      const preferred = verifiedAccounts[0];
      setSelectedAccountId(preferred ? String(preferred.id) : "");
      if (preferred) setSelectedRegion(preferred.default_region);
    }
  }, [awsAccounts, selectedAccountId, verifiedAccounts]);

  const handleAccountChange = (value: string) => {
    setSelectedAccountId(value);
    const matching = verifiedAccounts.find((acc) => String(acc.id) === value);
    if (matching?.default_region) {
      setSelectedRegion(matching.default_region);
    }
  };

  const handleStartScan = () => {
    if (scanMode === "aws") {
      if (!awsScanEnabled) {
        toast.error("Live AWS scanning unavailable", "This deployment has disabled AWS scanning.");
        return;
      }
      if (!selectedAccount) {
        toast.error(
          "Verified AWS account required",
          "Connect and verify an AWS account in Settings before starting a live scan."
        );
        navigate("/settings?tab=aws");
        return;
      }
      startScan({
        mode: "aws",
        aws_account_id: selectedAccount.id,
        region: selectedRegion,
      });
      return;
    }
    // Synthetic runs require the user to explicitly choose Synthetic above.
    startScan({ mode: "synthetic" });
  };

  const effectiveMode = isScanning ? activeScanMode ?? scanMode : scanMode;

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex flex-wrap items-center justify-end gap-2">
        {isGuestSimulation ? (
          <>
            <span className="inline-flex h-9 items-center rounded-md border border-border bg-card px-3 text-xs text-muted-foreground">
              <FlaskConical className="mr-2 h-3.5 w-3.5 text-primary" />
              Synthetic Demo Scan
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-9 gap-1.5 text-xs"
              onClick={() => {
                exitSimulationMode();
                navigate("/login");
              }}
              disabled={isScanning}
              title="Sign in to connect real AWS accounts and run live scans"
            >
              <LogIn className="h-3.5 w-3.5" />
              Sign in for Live AWS
            </Button>
          </>
        ) : awsScanEnabled ? (
          <Select
            value={scanMode}
            onValueChange={(value) => setSelectedScanMode(value as ScanMode)}
            disabled={isScanning}
          >
            <SelectTrigger className="h-9 w-[155px]">
              <SelectValue placeholder="Scan mode" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="synthetic">
                <span className="flex items-center gap-2">
                  <FlaskConical className="h-3.5 w-3.5" />
                  Synthetic
                </span>
              </SelectItem>
              <SelectItem value="aws">
                <span className="flex items-center gap-2">
                  <Cloud className="h-3.5 w-3.5" />
                  Live AWS
                </span>
              </SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <span className="inline-flex h-9 items-center rounded-md border border-border bg-card px-3 text-xs text-muted-foreground">
            <FlaskConical className="mr-2 h-3.5 w-3.5" />
            Synthetic only (hosted)
          </span>
        )}

        {awsScanEnabled && scanMode === "aws" && (
          <>
            <Select
              value={selectedAccountId}
              onValueChange={handleAccountChange}
              disabled={isScanning || verifiedAccounts.length === 0}
            >
              <SelectTrigger className="h-9 w-[210px]" title="Select connected AWS account">
                <SelectValue placeholder="AWS Account" />
              </SelectTrigger>
              <SelectContent>
                {verifiedAccounts.map((acc) => (
                  <SelectItem key={acc.id} value={String(acc.id)}>
                    {acc.display_name} ({acc.aws_account_id ?? acc.access_key_id_masked})
                  </SelectItem>
                ))}
                {verifiedAccounts.length === 0 && (
                  <SelectItem value="__no_verified_account__" disabled>
                    No verified AWS account
                  </SelectItem>
                )}
              </SelectContent>
            </Select>

            <Select
              value={selectedRegion}
              onValueChange={setSelectedRegion}
              disabled={isScanning}
            >
              <SelectTrigger className="h-9 w-[135px]" title="Select AWS Region">
                <SelectValue placeholder="Region" />
              </SelectTrigger>
              <SelectContent>
                {AWS_REGIONS.map((region) => (
                  <SelectItem key={region} value={region}>
                    {region}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-9 gap-1.5"
              onClick={() => navigate("/settings?tab=aws")}
              disabled={isScanning}
              title="Connect or manage AWS accounts"
            >
              <KeyRound className="h-3.5 w-3.5" />
              {awsAccounts && awsAccounts.length > 0 ? "Accounts" : "Connect AWS"}
            </Button>
          </>
        )}

        <Button
          onClick={handleStartScan}
          disabled={isScanning || (scanMode === "aws" && (!awsScanEnabled || !selectedAccount))}
          className="gap-2"
        >
          {isScanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
          {isScanning ? "Scanning…" : scanMode === "aws" ? "Run Live AWS Scan" : "Run Synthetic Scan"}
        </Button>
      </div>

      {awsScanEnabled && scanMode === "aws" && !selectedAccount && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Connect and verify an AWS account in Settings to enable live scans.
        </p>
      )}

      {(isScanning || scanStatus === "failed" || scanStatus === "completed") && steps.length > 0 && (
        <div className="w-full min-w-[260px] space-y-1.5 rounded-lg border border-border bg-card/80 px-3 py-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">
              {effectiveMode === "aws"
                ? `Live AWS scan (${selectedRegion})`
                : "Synthetic scan"}
            </span>
            <span className="font-mono tabular-nums text-foreground">{progress}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                scanStatus === "failed" ? "bg-red-500" : "bg-primary",
                isScanning && "animate-pulse"
              )}
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
          {currentStep && (
            <p className="truncate text-[11px] text-muted-foreground">{currentStep}</p>
          )}
          {steps.length > 0 && (
            <ol className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-border pt-2 text-[10px]">
              {steps.map((step) => {
                const Icon = step.status === "completed"
                  ? CheckCircle2
                  : step.status === "failed"
                    ? XCircle
                    : step.status === "running"
                      ? Loader2
                      : Circle;
                return (
                  <li key={step.name} className="flex min-w-0 items-center gap-1.5" title={step.error ?? step.name}>
                    <Icon className={cn(
                      "h-3 w-3 shrink-0",
                      step.status === "completed" && "text-emerald-500",
                      step.status === "failed" && "text-red-500",
                      step.status === "running" && "animate-spin text-primary",
                      step.status === "pending" && "text-muted-foreground/50"
                    )} />
                    <span className="truncate text-muted-foreground">{step.name}</span>
                  </li>
                );
              })}
            </ol>
          )}
          {scanStatus === "failed" && scanError && (
            <p className="text-[11px] text-red-500" role="alert">{scanError}</p>
          )}
        </div>
      )}
    </div>
  );
}
