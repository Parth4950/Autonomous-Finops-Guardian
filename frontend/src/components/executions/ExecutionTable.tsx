import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ExecutionItem } from "@/lib/api/types";
import {
  executionStatusBadgeVariant,
  STATUS_LABELS,
} from "@/lib/execution-transforms";
import { formatAction, formatTimestamp } from "@/lib/transforms";
import { formatCurrency } from "@/lib/utils";
import { ExternalLink } from "lucide-react";

interface ExecutionTableProps {
  data: ExecutionItem[];
  onOpenDetail: (execution: ExecutionItem) => void;
}

export function ExecutionTable({ data, onOpenDetail }: ExecutionTableProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <Table>
        <TableHeader>
          <TableRow className="bg-secondary/40 hover:bg-secondary/40">
            <TableHead>Execution ID</TableHead>
            <TableHead>Resource ID</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Timestamp</TableHead>
            <TableHead className="text-right">Estimated Savings</TableHead>
            <TableHead className="w-12" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((item) => (
            <TableRow
              key={item.execution_id}
              className="cursor-pointer"
              onClick={() => onOpenDetail(item)}
            >
              <TableCell className="font-mono text-xs">
                {item.status === "pending"
                  ? `pending-${item.approval_id.slice(0, 8)}`
                  : `${item.execution_id.slice(0, 8)}…`}
              </TableCell>
              <TableCell className="font-mono text-xs">{item.resource_id}</TableCell>
              <TableCell>
                <Badge variant="secondary">{formatAction(item.action)}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant={executionStatusBadgeVariant(item.status)}>
                  {STATUS_LABELS[item.status as keyof typeof STATUS_LABELS] ?? item.status}
                </Badge>
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {formatTimestamp(item.timestamp)}
              </TableCell>
              <TableCell className="text-right font-semibold tabular-nums text-emerald-400">
                {formatCurrency(item.estimated_savings ?? 0)}
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenDetail(item);
                  }}
                  aria-label="View execution details"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {data.length === 0 && (
            <TableRow>
              <TableCell colSpan={7} className="py-12 text-center text-muted-foreground">
                No executions match the current filters.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
