import { useMemo, useState } from "react";
import { ActionTypeDistributionChart } from "@/components/executions/ActionTypeDistributionChart";
import { ExecutionActivityFeed } from "@/components/executions/ExecutionActivityFeed";
import { ExecutionDetailModal } from "@/components/executions/ExecutionDetailModal";
import { ExecutionKpiCards } from "@/components/executions/ExecutionKpiCards";
import { ExecutionStatusChart } from "@/components/executions/ExecutionStatusChart";
import { ExecutionTable } from "@/components/executions/ExecutionTable";
import { ExecutionTimelineChart } from "@/components/executions/ExecutionTimelineChart";
import { ExecutionToolbar } from "@/components/executions/ExecutionToolbar";
import { SuccessRateTrendChart } from "@/components/executions/SuccessRateTrendChart";
import { ChartPanel } from "@/components/dashboard/OverviewWidgets";
import { PageHeader } from "@/components/shared/PageHeader";
import { QueryState } from "@/components/shared/QueryState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useExecutionsQuery } from "@/hooks/useApiQueries";
import type { ExecutionItem } from "@/lib/api/types";
import {
  buildActionTypeDistribution,
  buildExecutionTimeline,
  buildStatusDistribution,
  buildSuccessRateTrend,
  computeExecutionSummary,
  downloadLogs,
  filterExecutions,
  logsToText,
  parseActivityEvents,
  type ExecutionDateRange,
} from "@/lib/execution-transforms";
import { Terminal } from "lucide-react";

export default function ExecutionsPage() {
  const { data = [], isLoading, isError, error, refetch } = useExecutionsQuery();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("all");
  const [dateRange, setDateRange] = useState<ExecutionDateRange>("all");
  const [selectedExecution, setSelectedExecution] = useState<ExecutionItem | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const normalized = useMemo(
    () =>
      data.map((item) => ({
        ...item,
        estimated_savings: item.estimated_savings ?? 0,
        execution_steps: item.execution_steps ?? [],
        rollback_steps: item.rollback_steps ?? [],
        logs: item.logs ?? [],
        mode: item.mode ?? "simulation",
      })),
    [data]
  );

  const filtered = useMemo(
    () => filterExecutions(normalized, search, statusFilter, actionFilter, dateRange),
    [normalized, search, statusFilter, actionFilter, dateRange]
  );

  const summary = useMemo(() => computeExecutionSummary(normalized), [normalized]);
  const statusDistribution = useMemo(() => buildStatusDistribution(filtered), [filtered]);
  const actionDistribution = useMemo(() => buildActionTypeDistribution(filtered), [filtered]);
  const timeline = useMemo(() => buildExecutionTimeline(filtered), [filtered]);
  const successTrend = useMemo(() => buildSuccessRateTrend(filtered), [filtered]);
  const activityEvents = useMemo(() => parseActivityEvents(filtered), [filtered]);

  const uniqueActions = useMemo(
    () => Array.from(new Set(normalized.map((item) => item.action))).sort(),
    [normalized]
  );

  function handleOpenDetail(execution: ExecutionItem) {
    setSelectedExecution(execution);
    setModalOpen(true);
  }

  function handleDownloadAllLogs() {
    const content = filtered
      .map((item) => `=== ${item.execution_id} ===\n${logsToText(item)}`)
      .join("\n\n");
    const stamp = new Date().toISOString().slice(0, 10);
    downloadLogs(`finops-execution-logs-${stamp}.log`, content || "No logs available.");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Execution History"
        description="Track all remediation executions and outcomes — Datadog × AWS Systems Manager operations console"
      >
        <div className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs">
          <Terminal className="h-3.5 w-3.5 text-primary" />
          <span className="text-muted-foreground">Executor Agent</span>
          <span className="text-emerald-400">{summary.totalExecutions} completed</span>
          {summary.pending > 0 && (
            <span className="text-blue-400">· {summary.pending} pending</span>
          )}
        </div>
      </PageHeader>

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={!isLoading && normalized.length === 0}
        loadingMessage="Loading execution history..."
        emptyMessage="No executions recorded yet. Approve plans and run agents/executor/executor.py."
      >
        <>
          <ExecutionKpiCards
            totalExecutions={summary.totalExecutions}
            successful={summary.successful}
            failed={summary.failed}
            rollbacksGenerated={summary.rollbacksGenerated}
            totalSavings={summary.totalSavings}
          />

          <ExecutionToolbar
            search={search}
            onSearchChange={setSearch}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            actionFilter={actionFilter}
            onActionFilterChange={setActionFilter}
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            actions={uniqueActions}
            onDownloadAllLogs={handleDownloadAllLogs}
            recordCount={filtered.length}
          />

          <div className="grid gap-4 xl:grid-cols-2">
            <ChartPanel
              title="Execution Status Distribution"
              subtitle="Outcome breakdown across all executions"
            >
              {statusDistribution.length === 0 ? (
                <p className="py-12 text-center text-sm text-muted-foreground">No status data.</p>
              ) : (
                <ExecutionStatusChart data={statusDistribution} />
              )}
            </ChartPanel>

            <ChartPanel
              title="Action Type Distribution"
              subtitle="Remediation actions executed in this period"
            >
              {actionDistribution.length === 0 ? (
                <p className="py-12 text-center text-sm text-muted-foreground">No action data.</p>
              ) : (
                <ActionTypeDistributionChart data={actionDistribution} />
              )}
            </ChartPanel>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <ChartPanel
              title="Execution Timeline"
              subtitle="Cumulative executions over time"
            >
              {timeline.length === 0 ? (
                <p className="py-12 text-center text-sm text-muted-foreground">No timeline data.</p>
              ) : (
                <ExecutionTimelineChart data={timeline} />
              )}
            </ChartPanel>

            <ChartPanel
              title="Success Rate Trend"
              subtitle="Rolling success rate across execution sequence"
            >
              {successTrend.length === 0 ? (
                <p className="py-12 text-center text-sm text-muted-foreground">No trend data.</p>
              ) : (
                <SuccessRateTrendChart data={successTrend} />
              )}
            </ChartPanel>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>Execution History</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Click a row to view full execution details, logs, and rollback plan
                </p>
              </CardHeader>
              <CardContent>
                <ExecutionTable data={filtered} onOpenDetail={handleOpenDetail} />
              </CardContent>
            </Card>

            <ExecutionActivityFeed events={activityEvents} />
          </div>
        </>
      </QueryState>

      <ExecutionDetailModal
        execution={selectedExecution}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
}
