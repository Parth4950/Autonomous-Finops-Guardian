import { Button } from "@/components/ui/button";

import {

  Select,

  SelectContent,

  SelectItem,

  SelectTrigger,

  SelectValue,

} from "@/components/ui/select";

import { useCloudScan } from "@/hooks/useCloudScan";
import { useScanSource } from "@/hooks/useApiQueries";
import type { ScanMode } from "@/api/types";
import { cn } from "@/lib/utils";
import { Cloud, FlaskConical, Loader2, Radar } from "lucide-react";
import { useEffect, useState } from "react";

export function LiveScanButton() {
  const { data: scanSource } = useScanSource();
  const [scanMode, setScanMode] = useState<ScanMode>("synthetic");
  const { startScan, isScanning, progress, currentStep, scanMode: activeScanMode } =
    useCloudScan();

  useEffect(() => {
    if (scanSource?.mode === "aws" || scanSource?.mode === "synthetic") {
      setScanMode(scanSource.mode);
    }
  }, [scanSource?.mode]);



  const effectiveMode = isScanning ? activeScanMode ?? scanMode : scanMode;



  return (

    <div className="flex flex-col items-end gap-2">

      <div className="flex flex-wrap items-center justify-end gap-2">

        <Select

          value={scanMode}

          onValueChange={(value) => setScanMode(value as ScanMode)}

          disabled={isScanning}

        >

          <SelectTrigger className="h-9 w-[170px]">

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



        <Button

          onClick={() => startScan(scanMode)}

          disabled={isScanning}

          className="gap-2"

        >

          {isScanning ? (

            <Loader2 className="h-4 w-4 animate-spin" />

          ) : (

            <Radar className="h-4 w-4" />

          )}

          {isScanning ? "Scanning…" : "Run Cloud Scan"}

        </Button>

      </div>



      {isScanning && (

        <div className="w-full min-w-[260px] space-y-1.5 rounded-lg border border-border bg-card/80 px-3 py-2">

          <div className="flex items-center justify-between text-xs">

            <span className="text-muted-foreground">

              {effectiveMode === "aws" ? "Live AWS scan" : "Synthetic scan"}

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

          {effectiveMode === "aws" && currentStep?.toLowerCase().includes("aws") && (

            <p className="text-[10px] text-muted-foreground/80">

              Discovering EC2/EBS and collecting CloudWatch metrics — this may take several minutes.

            </p>

          )}

          {currentStep?.toLowerCase().includes("forecast") && (

            <p className="text-[10px] text-muted-foreground/80">

              Prophet trains per-resource models — duration depends on instance count.

            </p>

          )}

        </div>

      )}

    </div>

  );

}

