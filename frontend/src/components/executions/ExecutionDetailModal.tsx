import { useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  executionStatusBadgeVariant,
  logsToText,
  STATUS_LABELS,
  downloadLogs,
} from "@/lib/execution-transforms";
import type { ExecutionItem } from "@/lib/api/types";
import { formatAction, formatRiskLevel, riskBadgeVariant } from "@/lib/transforms";
import { formatCurrency } from "@/lib/utils";
import { formatTimestamp } from "@/lib/transforms";
import {
  AlertTriangle,
  Download,
  FileText,
  RotateCcw,
  Terminal,
  X,
} from "lucide-react";

interface ExecutionDetailModalProps {
  execution: ExecutionItem | null;
  open: boolean;
  onClose: () => void;
}

export function ExecutionDetailModal({ execution, open, onClose }: ExecutionDetailModalProps) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open || !execution) return null;

  function handleDownloadLog() {
    const content = logsToText(execution!);
    const stamp = execution!.execution_id.slice(0, 8);
    downloadLogs(`execution-${stamp}.log`, content);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close modal"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="execution-modal-title"
        className="relative flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-border bg-[#161A1F] shadow-2xl"
      >
        <div className="flex items-start justify-between border-b border-border px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Execution Details
            </p>
            <h2 id="execution-modal-title" className="mt-1 font-mono text-lg font-semibold">
              {execution.execution_id.slice(0, 13)}…
            </h2>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant={executionStatusBadgeVariant(execution.status)}>
                {STATUS_LABELS[execution.status as keyof typeof STATUS_LABELS] ??
                  execution.status}
              </Badge>
              <Badge variant="secondary">{formatAction(execution.action)}</Badge>
              <Badge variant="outline">{execution.mode ?? "simulation"}</Badge>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <MetaBlock label="Resource ID" value={execution.resource_id} mono />
            <MetaBlock label="Timestamp" value={formatTimestamp(execution.timestamp)} />
            <MetaBlock
              label="Savings Estimate"
              value={formatCurrency(execution.estimated_savings ?? 0)}
              accent
            />
          </div>

          <section className="rounded-lg border border-border bg-card/50 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              Risk Assessment
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted-foreground">Risk Level</p>
                <Badge variant={riskBadgeVariant(execution.risk_level ?? "low")} className="mt-1 capitalize">
                  {execution.risk_level ?? "unknown"}
                </Badge>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Risk Score</p>
                <p className="mt-1 font-mono">{execution.risk_score ?? "—"}/100</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Environment</p>
                <p className="mt-1 text-sm">{formatRiskLevel(execution.risk_level ?? "unknown")}</p>
              </div>
            </div>
            {execution.risk_explanation && (
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {execution.risk_explanation}
              </p>
            )}
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <FileText className="h-4 w-4 text-blue-400" />
              Execution Steps
            </div>
            <ol className="space-y-2">
              {(execution.execution_steps ?? []).map((step, index) => (
                <li
                  key={step}
                  className="flex gap-3 rounded-md border border-border bg-card/40 px-3 py-2 text-sm"
                >
                  <span className="font-mono text-xs text-muted-foreground">{index + 1}.</span>
                  {step}
                </li>
              ))}
              {(execution.execution_steps ?? []).length === 0 && (
                <p className="text-sm text-muted-foreground">No execution steps recorded.</p>
              )}
            </ol>
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Terminal className="h-4 w-4 text-emerald-400" />
                Logs
              </div>
              <Button variant="outline" size="sm" onClick={handleDownloadLog}>
                <Download className="mr-2 h-3.5 w-3.5" />
                Download
              </Button>
            </div>
            <pre className="max-h-48 overflow-auto rounded-lg border border-border bg-[#0D1117] p-4 font-mono text-xs leading-relaxed text-emerald-300/90">
              {logsToText(execution)}
            </pre>
            {execution.error_message && (
              <p className="mt-2 text-sm text-red-400">{execution.error_message}</p>
            )}
          </section>

          {(execution.rollback_steps ?? []).length > 0 && (
            <section className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <RotateCcw className="h-4 w-4 text-amber-400" />
                Rollback Plan
              </div>
              <ol className="space-y-1.5">
                {(execution.rollback_steps ?? []).map((step, index) => (
                  <li key={step} className="flex gap-2 text-sm text-foreground/90">
                    <span className="font-mono text-xs text-muted-foreground">{index + 1}.</span>
                    {step}
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>

        <div className="border-t border-border px-6 py-4">
          <Button className="w-full" variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}

function MetaBlock({
  label,
  value,
  mono,
  accent,
}: {
  label: string;
  value: string;
  mono?: boolean;
  accent?: boolean;
}) {
  return (
    <div className="rounded-md border border-border bg-card/40 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={`mt-0.5 text-sm ${mono ? "font-mono" : ""} ${
          accent ? "font-semibold text-emerald-400" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}
