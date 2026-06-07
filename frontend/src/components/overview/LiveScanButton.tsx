import { Button } from "@/components/ui/button";
import { useCloudScan } from "@/hooks/useCloudScan";
import { cn } from "@/lib/utils";
import { Loader2, Radar } from "lucide-react";

export function LiveScanButton() {
  const { startScan, isScanning, progress, currentStep } = useCloudScan();

  return (
    <div className="flex flex-col items-end gap-2">
      <Button
        onClick={() => startScan()}
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

      {isScanning && (
        <div className="w-full min-w-[220px] space-y-1.5 rounded-lg border border-border bg-card/80 px-3 py-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Scanning…</span>
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
