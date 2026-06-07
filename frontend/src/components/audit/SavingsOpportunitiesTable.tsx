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
import type { AuditResultItem } from "@/lib/api/types";
import {
  filterAuditResults,
  recommendationBadgeVariant,
  riskBadgeVariant,
} from "@/lib/audit-transforms";
import { formatCurrency } from "@/lib/utils";
import { Search } from "lucide-react";

interface SavingsOpportunitiesTableProps {
  data: AuditResultItem[];
}

export function SavingsOpportunitiesTable({ data }: SavingsOpportunitiesTableProps) {
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");
  const [recommendationFilter, setRecommendationFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");

  const recommendations = useMemo(
    () => Array.from(new Set(data.map((item) => item.recommendation))).sort(),
    [data]
  );
  const priorities = useMemo(
    () => Array.from(new Set(data.map((item) => item.priority_category))).sort(),
    [data]
  );

  const filtered = useMemo(
    () => filterAuditResults(data, search, riskFilter, recommendationFilter, priorityFilter),
    [data, search, riskFilter, recommendationFilter, priorityFilter]
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search resources..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <Select value={riskFilter} onValueChange={setRiskFilter}>
          <SelectTrigger className="h-9 w-[130px]">
            <SelectValue placeholder="Risk" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Risk</SelectItem>
            <SelectItem value="low">Low</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="high">High</SelectItem>
          </SelectContent>
        </Select>

        <Select value={recommendationFilter} onValueChange={setRecommendationFilter}>
          <SelectTrigger className="h-9 w-[180px]">
            <SelectValue placeholder="Recommendation" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Recommendations</SelectItem>
            {recommendations.map((rec) => (
              <SelectItem key={rec} value={rec}>
                {rec}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={priorityFilter} onValueChange={setPriorityFilter}>
          <SelectTrigger className="h-9 w-[200px]">
            <SelectValue placeholder="Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Priorities</SelectItem>
            {priorities.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow className="bg-secondary/40 hover:bg-secondary/40">
              <TableHead>Resource ID</TableHead>
              <TableHead className="text-right">Monthly Cost</TableHead>
              <TableHead className="text-right">Annual Cost</TableHead>
              <TableHead className="text-right">Waste Score</TableHead>
              <TableHead>Risk Level</TableHead>
              <TableHead className="text-right">Priority Score</TableHead>
              <TableHead className="text-right">Potential Savings</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((row) => (
              <TableRow key={row.resource_id}>
                <TableCell>
                  <div>
                    <p className="font-mono text-xs">{row.resource_id}</p>
                    <Badge variant={recommendationBadgeVariant(row.recommendation)} className="mt-1 text-[10px]">
                      {row.recommendation}
                    </Badge>
                  </div>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatCurrency(row.monthly_cost)}
                </TableCell>
                <TableCell className="text-right tabular-nums text-muted-foreground">
                  {formatCurrency(row.annual_cost)}
                </TableCell>
                <TableCell className="text-right tabular-nums">{row.waste_score.toFixed(1)}%</TableCell>
                <TableCell>
                  <Badge variant={riskBadgeVariant(row.risk_level)} className="capitalize">
                    {row.risk_level}
                  </Badge>
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums">
                  {row.priority_score.toFixed(1)}
                </TableCell>
                <TableCell className="text-right">
                  <p className="font-semibold tabular-nums text-emerald-400">
                    {formatCurrency(row.potential_annual_savings)}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {formatCurrency(row.potential_monthly_savings)}/mo
                  </p>
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-12 text-center text-muted-foreground">
                  No savings opportunities match the current filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <p className="text-xs text-muted-foreground">
        Showing {filtered.length} of {data.length} top savings opportunities
      </p>
    </div>
  );
}
