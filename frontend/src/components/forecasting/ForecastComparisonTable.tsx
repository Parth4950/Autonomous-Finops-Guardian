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
import type { ForecastResource } from "@/api/types";
import {
  cpuDelta,
  formatCategory,
  wasteBadgeVariant,
} from "@/lib/forecast-transforms";
import { Search, TrendingDown, TrendingUp } from "lucide-react";

interface ForecastComparisonTableProps {
  data: ForecastResource[];
}

type SortKey = "forecast_avg_cpu" | "historical_avg_cpu" | "delta" | "resource_id";
type SortDir = "asc" | "desc";

const PAGE_SIZE = 12;

export function ForecastComparisonTable({ data }: ForecastComparisonTableProps) {
  const [search, setSearch] = useState("");
  const [wasteFilter, setWasteFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("forecast_avg_cpu");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    const rows = data.filter((row) => {
      const matchesSearch =
        search === "" || row.resource_id.toLowerCase().includes(search.toLowerCase());
      const matchesWaste = wasteFilter === "all" || row.waste_probability === wasteFilter;
      const matchesType = typeFilter === "all" || row.resource_type === typeFilter;
      return matchesSearch && matchesWaste && matchesType;
    });

    return rows.sort((a, b) => {
      const deltaA = cpuDelta(a.historical_avg_cpu, a.forecast_avg_cpu);
      const deltaB = cpuDelta(b.historical_avg_cpu, b.forecast_avg_cpu);
      let cmp = 0;

      if (sortKey === "resource_id") {
        cmp = a.resource_id.localeCompare(b.resource_id);
      } else if (sortKey === "delta") {
        cmp = deltaA - deltaB;
      } else {
        cmp = a[sortKey] - b[sortKey];
      }

      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data, search, wasteFilter, typeFilter, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageData = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "resource_id" ? "asc" : "asc");
    }
    setPage(0);
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return null;
    return sortDir === "asc" ? " ↑" : " ↓";
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
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
          value={wasteFilter}
          onValueChange={(v) => {
            setWasteFilter(v);
            setPage(0);
          }}
        >
          <SelectTrigger className="h-9 w-[160px]">
            <SelectValue placeholder="Waste probability" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Waste Levels</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={typeFilter}
          onValueChange={(v) => {
            setTypeFilter(v);
            setPage(0);
          }}
        >
          <SelectTrigger className="h-9 w-[140px]">
            <SelectValue placeholder="Resource type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="healthy">Healthy</SelectItem>
            <SelectItem value="zombie">Zombie</SelectItem>
            <SelectItem value="seasonal">Seasonal</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead
                className="cursor-pointer select-none"
                onClick={() => toggleSort("resource_id")}
              >
                Resource ID{sortIndicator("resource_id")}
              </TableHead>
              <TableHead>Type</TableHead>
              <TableHead
                className="cursor-pointer select-none text-right"
                onClick={() => toggleSort("historical_avg_cpu")}
              >
                Historical CPU{sortIndicator("historical_avg_cpu")}
              </TableHead>
              <TableHead
                className="cursor-pointer select-none text-right"
                onClick={() => toggleSort("forecast_avg_cpu")}
              >
                Forecast Avg CPU{sortIndicator("forecast_avg_cpu")}
              </TableHead>
              <TableHead
                className="cursor-pointer select-none text-right"
                onClick={() => toggleSort("delta")}
              >
                Delta{sortIndicator("delta")}
              </TableHead>
              <TableHead>Utilization</TableHead>
              <TableHead>Waste Probability</TableHead>
              <TableHead className="text-right">Forecast Range</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageData.map((row) => {
              const delta = cpuDelta(row.historical_avg_cpu, row.forecast_avg_cpu);
              const rising = delta > 0.5;
              const falling = delta < -0.5;

              return (
                <TableRow key={row.resource_id}>
                  <TableCell className="font-mono text-xs">{row.resource_id}</TableCell>
                  <TableCell className="capitalize">{row.resource_type}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {row.historical_avg_cpu.toFixed(2)}%
                  </TableCell>
                  <TableCell className="text-right tabular-nums font-medium">
                    {row.forecast_avg_cpu.toFixed(2)}%
                  </TableCell>
                  <TableCell className="text-right">
                    <span
                      className={`inline-flex items-center gap-1 tabular-nums ${
                        rising ? "text-emerald-400" : falling ? "text-red-400" : "text-muted-foreground"
                      }`}
                    >
                      {rising && <TrendingUp className="h-3 w-3" />}
                      {falling && <TrendingDown className="h-3 w-3" />}
                      {delta > 0 ? "+" : ""}
                      {delta.toFixed(2)}%
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{formatCategory(row.utilization_category)}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={wasteBadgeVariant(row.waste_probability)}>
                      {row.waste_probability}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">
                    {row.forecast_min_cpu.toFixed(1)} – {row.forecast_max_cpu.toFixed(1)}%
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{filtered.length} resource(s)</span>
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
