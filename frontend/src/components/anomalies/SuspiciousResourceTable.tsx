import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
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
import type { AnomalyPrediction } from "@/api/types";
import {
  formatNetwork,
  formatPrediction,
  scoreSeverity,
} from "@/lib/forecast-transforms";
import { formatCurrency } from "@/lib/utils";
import { Search } from "lucide-react";

interface SuspiciousResourceTableProps {
  data: AnomalyPrediction[];
}

const PAGE_SIZE = 10;

function severityVariant(severity: ReturnType<typeof scoreSeverity>) {
  if (severity === "critical") return "destructive" as const;
  if (severity === "high") return "destructive" as const;
  if (severity === "medium") return "warning" as const;
  return "secondary" as const;
}

export function SuspiciousResourceTable({ data }: SuspiciousResourceTableProps) {
  const [search, setSearch] = useState("");
  const [labelFilter, setLabelFilter] = useState("all");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    return data.filter((row) => {
      const matchesSearch =
        search === "" ||
        row.resource_id.toLowerCase().includes(search.toLowerCase()) ||
        row.resource_label.toLowerCase().includes(search.toLowerCase());
      const matchesLabel = labelFilter === "all" || row.resource_label === labelFilter;
      return matchesSearch && matchesLabel;
    });
  }, [data, search, labelFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageData = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  const labels = useMemo(
    () => Array.from(new Set(data.map((d) => d.resource_label))).sort(),
    [data]
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search resources..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="pl-9"
          />
        </div>
        <Select
          value={labelFilter}
          onValueChange={(v) => {
            setLabelFilter(v);
            setPage(0);
          }}
        >
          <SelectTrigger className="h-9 w-[160px]">
            <SelectValue placeholder="Ground truth label" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Labels</SelectItem>
            {labels.map((l) => (
              <SelectItem key={l} value={l}>
                {l}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Resource ID</TableHead>
              <TableHead className="text-right">Anomaly Score</TableHead>
              <TableHead>Prediction</TableHead>
              <TableHead className="text-right">CPU %</TableHead>
              <TableHead className="text-right">Network In</TableHead>
              <TableHead className="text-right">Network Out</TableHead>
              <TableHead>Label</TableHead>
              <TableHead className="text-right">Cost/mo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageData.map((row) => {
              const severity = scoreSeverity(row.anomaly_score);
              return (
                <TableRow key={row.resource_id}>
                  <TableCell className="font-mono text-xs">{row.resource_id}</TableCell>
                  <TableCell className="text-right">
                    <span className="font-mono text-red-400">{row.anomaly_score.toFixed(4)}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="destructive">{formatPrediction(row.prediction)}</Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{row.avg_cpu.toFixed(2)}</TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">
                    {formatNetwork(row.avg_network_in)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">
                    {formatNetwork(row.avg_network_out)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={severityVariant(severity)}>{row.resource_label}</Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatCurrency(row.monthly_cost)}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {filtered.length} suspicious resource(s)
        </span>
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
