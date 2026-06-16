import { Beaker, Cloud, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ScanMode } from "@/api/types";

interface DataModeNoticeProps {
  variant?: "banner" | "inline";
  className?: string;
  scanMode?: ScanMode | null;
}

export function DataModeNotice({ variant = "banner", className, scanMode = "synthetic" }: DataModeNoticeProps) {
  const isAws = scanMode === "aws";

  if (variant === "inline") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[10px] font-medium",
          isAws
            ? "border-sky-500/25 bg-sky-500/10 text-sky-200"
            : "border-amber-500/25 bg-amber-500/10 text-amber-200",
          className
        )}
      >
        {isAws ? <Cloud className="h-3 w-3" /> : <Beaker className="h-3 w-3" />}
        {isAws ? "Live AWS" : "Synthetic data"}
      </span>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3 text-sm",
        isAws
          ? "border-sky-500/20 bg-sky-500/5"
          : "border-amber-500/20 bg-amber-500/5",
        className
      )}
    >
      <div className={cn("flex items-center gap-2", isAws ? "text-sky-200" : "text-amber-200")}>
        {isAws ? <Cloud className="h-4 w-4 shrink-0" /> : <Beaker className="h-4 w-4 shrink-0" />}
        <span className="font-medium">{isAws ? "Live AWS discovery" : "Synthetic pipeline"}</span>
      </div>
      <p className="text-xs text-muted-foreground">
        {isAws ? (
          <>
            Scout Agent discovers EC2/EBS in your AWS account and collects CloudWatch metrics.
            Remediation still runs in{" "}
          </>
        ) : (
          <>
            Resources and metrics are generated locally — not live AWS. Remediation runs in{" "}
          </>
        )}
        <span className="inline-flex items-center gap-1 text-foreground">
          <ShieldCheck className="h-3 w-3" />
          simulation mode
        </span>{" "}
        (no real infrastructure changes).
      </p>
    </div>
  );
}
