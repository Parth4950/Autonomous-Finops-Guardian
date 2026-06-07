import { useMemo, useState } from "react";
import { ApprovalStatusBadge } from "@/components/approvals/ApprovalStatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ApprovalItem } from "@/lib/api/types";
import {
  formatAction,
  formatTimestamp,
  riskBadgeVariant,
} from "@/lib/transforms";
import { formatCurrency } from "@/lib/utils";
import { Check, Loader2, Search, ShieldAlert, X } from "lucide-react";

interface ApprovalQueueTableProps {
  data: ApprovalItem[];
  loadingId: string | null;
  onApprove: (approvalId: string) => void;
  onReject: (approvalId: string) => void;
}

const PAGE_SIZE = 10;

export function ApprovalQueueTable({
  data,
  loadingId,
  onApprove,
  onReject,
}: ApprovalQueueTableProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    return data.filter((row) => {
      const matchesSearch =
        search === "" ||
        row.resource_id.toLowerCase().includes(search.toLowerCase()) ||
        row.action.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === "all" || row.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [data, search, statusFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageData = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search resource or action..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="pl-9"
          />
        </div>

        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v);
            setPage(0);
          }}
        >
          <SelectTrigger className="h-9 w-[160px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
            <SelectItem value="executed">Executed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow className="bg-secondary/40 hover:bg-secondary/40">
              <TableHead>Resource</TableHead>
              <TableHead>Action</TableHead>
              <TableHead className="text-right">Savings</TableHead>
              <TableHead>Risk Level</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Reviewer</TableHead>
              <TableHead className="text-right">Governance</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageData.map((row) => {
              const isPending = row.status === "pending";
              const isLoading = loadingId === row.approval_id;

              return (
                <TableRow key={row.approval_id} className="group">
                  <TableCell>
                    <div className="space-y-1">
                      <p className="font-mono text-xs font-medium">{row.resource_id}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {row.approval_id.slice(0, 8)}…
                      </p>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-normal">
                      {formatAction(row.action)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <span className="font-semibold tabular-nums text-emerald-400">
                      {formatCurrency(row.estimated_savings)}
                    </span>
                    <p className="text-[10px] text-muted-foreground">annual</p>
                  </TableCell>
                  <TableCell>
                    <Badge variant={riskBadgeVariant(row.risk_level)} className="capitalize">
                      {row.risk_level}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <ApprovalStatusBadge status={row.status} />
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {row.reviewed_by ?? "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    {isPending ? (
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isLoading}
                          className="h-8 border-emerald-500/30 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 hover:text-emerald-300"
                          onClick={() => onApprove(row.approval_id)}
                        >
                          {isLoading ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Check className="h-3 w-3" />
                          )}
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isLoading}
                          className="h-8 border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300"
                          onClick={() => onReject(row.approval_id)}
                        >
                          {isLoading ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <X className="h-3 w-3" />
                          )}
                          Reject
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        {formatTimestamp(row.updated_at)}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
            {pageData.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-12 text-center text-muted-foreground">
                  <ShieldAlert className="mx-auto mb-2 h-5 w-5 opacity-50" />
                  No approval requests match the current filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{filtered.length} request(s)</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="rounded border border-border px-2 py-1 disabled:opacity-40"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            Prev
          </button>
          <span>
            Page {page + 1} / {totalPages}
          </span>
          <button
            type="button"
            className="rounded border border-border px-2 py-1 disabled:opacity-40"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
