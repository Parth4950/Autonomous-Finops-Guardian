import { ApprovalStatusBadge } from "@/components/approvals/ApprovalStatusBadge";
import { ApprovalHistoryTimeline } from "@/components/approvals/ApprovalHistoryTimeline";
import { ApprovalQueueTable } from "@/components/approvals/ApprovalQueueTable";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard, PageHeader } from "@/components/shared/PageHeader";
import { QueryState } from "@/components/shared/QueryState";
import { useApproveMutation, useRejectMutation } from "@/hooks/useApprovalMutations";
import { useApprovalsQuery } from "@/hooks/useApiQueries";
import { buildApprovalHistory, computeApprovalStats } from "@/lib/transforms";
import { formatCurrency } from "@/lib/utils";
import { CheckCircle2, Clock, Shield, XCircle, Zap } from "lucide-react";
import { useMemo, useState } from "react";

const WORKFLOW_STEPS = [
  { key: "pending", label: "Pending Review", icon: Clock },
  { key: "approved", label: "Approved", icon: CheckCircle2 },
  { key: "executed", label: "Executed", icon: Zap },
] as const;

export default function ApprovalsPage() {
  const { data = [], isLoading, isError, error, refetch, isFetching } = useApprovalsQuery();
  const approveMutation = useApproveMutation();
  const rejectMutation = useRejectMutation();
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const stats = useMemo(() => computeApprovalStats(data), [data]);
  const history = useMemo(() => buildApprovalHistory(data), [data]);
  const loadingId =
    approveMutation.isPending
      ? approveMutation.variables?.approvalId ?? null
      : rejectMutation.isPending
        ? rejectMutation.variables?.approvalId ?? null
        : null;

  async function handleApprove(approvalId: string) {
    setMessage(null);
    try {
      const updated = await approveMutation.mutateAsync({
        approvalId,
        notes: "Approved via Approval Center",
      });
      setMessage({ type: "success", text: `Approved remediation for ${updated.resource_id}` });
    } catch (err) {
      setMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Approval failed",
      });
    }
  }

  async function handleReject(approvalId: string) {
    setMessage(null);
    const notes =
      window.prompt("Rejection notes (optional):", "Requires additional validation.") ??
      "Rejected via Approval Center";

    try {
      const updated = await rejectMutation.mutateAsync({ approvalId, notes });
      setMessage({ type: "success", text: `Rejected remediation for ${updated.resource_id}` });
    } catch (err) {
      setMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Rejection failed",
      });
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Approval Center"
        description="Human-in-the-loop governance — review remediation plans before execution"
      >
        <div className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs">
          <Shield className="h-3.5 w-3.5 text-primary" />
          <span className="text-muted-foreground">FastAPI</span>
          <span className={isError ? "text-red-400" : "text-emerald-400"}>
            {isError ? "Disconnected" : isFetching ? "Syncing..." : "Connected"}
          </span>
        </div>
      </PageHeader>

      {message && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            message.type === "success"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-red-500/30 bg-red-500/10 text-red-300"
          }`}
        >
          {message.text}
        </div>
      )}

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={!isLoading && data.length === 0}
        loadingMessage="Loading approval queue..."
        emptyMessage="No approval requests in the queue."
      >
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <MetricCard label="Pending" value={stats.pending} subtext="Awaiting review" />
            <MetricCard label="Approved" value={stats.approved} subtext="Ready for execution" />
            <MetricCard label="Rejected" value={stats.rejected} subtext="Blocked actions" />
            <MetricCard label="Executed" value={stats.executed} subtext="Completed remediations" />
            <MetricCard
              label="Pending Savings"
              value={formatCurrency(stats.pending_savings)}
              subtext={`${formatCurrency(stats.approved_savings)} approved`}
            />
          </div>

          <Card className="border-primary/20 bg-gradient-to-r from-card via-card to-primary/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Governance Workflow</CardTitle>
              <p className="text-xs text-muted-foreground">
                Planner packages enter the queue as pending — approvers gate execution
              </p>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                {WORKFLOW_STEPS.map((step, index) => {
                  const Icon = step.icon;
                  const count =
                    step.key === "pending"
                      ? stats.pending
                      : step.key === "approved"
                        ? stats.approved + stats.executed
                        : stats.executed;

                  return (
                    <div key={step.key} className="flex flex-1 items-center gap-3">
                      <div className="flex items-center gap-3 rounded-lg border border-border bg-background/60 px-4 py-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/15">
                          <Icon className="h-4 w-4 text-primary" />
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">{step.label}</p>
                          <p className="text-lg font-semibold tabular-nums">{count}</p>
                        </div>
                      </div>
                      {index < WORKFLOW_STEPS.length - 1 && (
                        <div className="hidden h-px flex-1 bg-border md:block" />
                      )}
                    </div>
                  );
                })}
                <div className="flex items-center gap-3 rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3">
                  <XCircle className="h-5 w-5 text-red-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">Rejected</p>
                    <p className="text-lg font-semibold tabular-nums text-red-400">{stats.rejected}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <CardTitle>Approval Queue</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    Review resource, action, savings, and risk level before approving remediation
                  </p>
                </div>
                <ApprovalStatusBadge status="pending" />
              </div>
            </CardHeader>
            <CardContent>
              <ApprovalQueueTable
                data={data}
                loadingId={loadingId}
                onApprove={handleApprove}
                onReject={handleReject}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Approval History</CardTitle>
              <p className="text-xs text-muted-foreground">
                Reviewed requests — {history.length} event(s) derived from approval records
              </p>
            </CardHeader>
            <CardContent>
              {history.length === 0 ? (
                <QueryState
                  isLoading={false}
                  isError={false}
                  isEmpty
                  emptyMessage="No reviewed approvals yet."
                />
              ) : (
                <ApprovalHistoryTimeline events={history} />
              )}
            </CardContent>
          </Card>
        </>
      </QueryState>
    </div>
  );
}
