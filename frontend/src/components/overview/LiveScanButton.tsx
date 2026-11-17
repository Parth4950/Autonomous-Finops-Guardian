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
import { Cloud, FlaskConical, KeyRound, Loader2, LogIn, Radar } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const ENV_DEFAULT_ACCOUNT = "__env_default__";

export function LiveScanButton() {
  const navigate = useNavigate();
  const { user, isSimulationMode, exitSimulationMode } = useAuth();
  const isGuestSimulation = isSimulationMode && !user;
  const { data: scanSource } = useScanSource();
  const { data: health } = useHealth();
  const { data: awsAccounts } = useAwsAccounts(!isGuestSimulation);
  const awsScanEnabled = (health?.aws_scan_enabled ?? true) && !isGuestSimulation;
  const [scanMode, setScanMode] = useState<ScanMode>("synthetic");
  const [selectedAccountId, setSelectedAccountId] = useState<string>(ENV_DEFAULT_ACCOUNT);
  const [selectedRegion, setSelectedRegion] = useState<string>("us-east-1");
  const { startScan, isScanning, progress, currentStep, scanMode: activeScanMode } =
    useCloudScan();

  useEffect(() => {
    if (!awsScanEnabled) {
      setScanMode("synthetic");
      return;
    }
    if (scanSource?.mode === "aws" || scanSource?.mode === "synthetic") {
      setScanMode(scanSource.mode);
    }
    if (scanSource?.region) {
      setSelectedRegion(scanSource.region);
    }
  }, [awsScanEnabled, scanSource?.mode, scanSource?.region]);

  useEffect(() => {
    if (!awsAccounts || awsAccounts.length === 0) {
      if (selectedAccountId !== ENV_DEFAULT_ACCOUNT) {
        setSelectedAccountId(ENV_DEFAULT_ACCOUNT);
      }
      return;
    }
    const stillExists = awsAccounts.some((acc) => String(acc.id) === selectedAccountId);
    if (selectedAccountId === ENV_DEFAULT_ACCOUNT || !stillExists) {
      const preferred =
        awsAccounts.find((acc) => acc.verification_status === "verified") ?? awsAccounts[0];
      if (preferred) {
        setSelectedAccountId(String(preferred.id));
        setSelectedRegion(preferred.default_region);
      }
    }
  }, [awsAccounts, selectedAccountId]);

  const handleAccountChange = (value: string) => {
    setSelectedAccountId(value);
    const matching = awsAccounts?.find((acc) => String(acc.id) === value);
    if (matching?.default_region) {
      setSelectedRegion(matching.default_region);
    }
  };

  const handleStartScan = () => {
    if (scanMode === "aws" && awsScanEnabled) {
      startScan({
        mode: "aws",
        aws_account_id:
          selectedAccountId !== ENV_DEFAULT_ACCOUNT ? Number(selectedAccountId) : null,
        region: selectedRegion,
      });
      return;
    }
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
            onValueChange={(value) => setScanMode(value as ScanMode)}
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
              disabled={isScanning}
            >
              <SelectTrigger className="h-9 w-[210px]" title="Select connected AWS account">
                <SelectValue placeholder="AWS Account" />
              </SelectTrigger>
              <SelectContent>
                {awsAccounts?.map((acc) => (
                  <SelectItem key={acc.id} value={String(acc.id)}>
                    {acc.display_name} ({acc.aws_account_id ?? acc.access_key_id_masked})
                  </SelectItem>
                ))}
                <SelectItem value={ENV_DEFAULT_ACCOUNT}>
                  Host Environment Credentials
                </SelectItem>
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

        <Button onClick={handleStartScan} disabled={isScanning} className="gap-2">
          {isScanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
          {isScanning ? "Scanning…" : "Run Cloud Scan"}
        </Button>
      </div>

      {isScanning && (
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
                "h-full rounded-full bg-primary transition-all duration-500",
                progress < 100 && "animate-pulse"
              )}
              style={{ width: `${Math.max(progress, 8)}%` }}
            />
          </div>
          {currentStep && (
            <p className="truncate text-[11px] text-muted-foreground">{currentStep}</p>
          )}
        </div>
      )}
    </div>
  );
}
