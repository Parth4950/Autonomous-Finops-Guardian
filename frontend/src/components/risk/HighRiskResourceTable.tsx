import { Fragment, useMemo, useState } from "react";
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
import type { RiskAssessmentItem } from "@/lib/api/types";
import {
  formatRiskLevel,
  riskBadgeVariant,
} from "@/lib/transforms";
import { formatCurrency } from "@/lib/utils";
import { ChevronDown, ChevronRight, Search } from "lucide-react";

interface HighRiskResourceTableProps {
  data: RiskAssessmentItem[];
}

const PAGE_SIZE = 8;

function recommendationBadgeVariant(
  recommendation: string
): "destructive" | "warning" | "success" {
  if (recommendation === "Do Not Remediate") return "destructive";
  if (recommendation === "Manual Review Required") return "warning";
  return "success";
}

export function HighRiskResourceTable({ data }: HighRiskResourceTableProps) {
  const [search, setSearch] = useState("");
  const [envFilter, setEnvFilter] = useState("all");
  const [page, setPage] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    return data.filter((row) => {
      const matchesSearch =
        search === "" ||
        row.resource_id.toLowerCase().includes(search.toLowerCase()) ||
        row.risk_explanation.toLowerCase().includes(search.toLowerCase());
      const matchesEnv = envFilter === "all" || row.environment === envFilter;
      return matchesSearch && matchesEnv;
    });
  }, [data, search, envFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageData = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  function toggleExpand(resourceId: string) {
    setExpandedId((current) => (current === resourceId ? null : resourceId));
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search resources or explanations..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="pl-9"
          />
        </div>

        <Select
          value={envFilter}
          onValueChange={(v) => {
            setEnvFilter(v);
            setPage(0);
          }}
        >
          <SelectTrigger className="h-9 w-[160px]">
            <SelectValue placeholder="Environment" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Environments</SelectItem>
            <SelectItem value="production">Production</SelectItem>
            <SelectItem value="staging">Staging</SelectItem>
            <SelectItem value="development">Development</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead>Resource ID</TableHead>
              <TableHead>Environment</TableHead>
              <TableHead className="text-right">Waste Score</TableHead>
              <TableHead className="text-right">Risk Score</TableHead>
              <TableHead>Risk Level</TableHead>
              <TableHead>Recommendation</TableHead>
              <TableHead className="text-right">Cost/mo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageData.map((row) => {
              const isExpanded = expandedId === row.resource_id;

              return (
                <Fragment key={row.resource_id}>
                  <TableRow className="cursor-pointer hover:bg-muted/30">
                    <TableCell onClick={() => toggleExpand(row.resource_id)}>
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
                    </TableCell>
                    <TableCell
                      className="font-mono text-xs"
                      onClick={() => toggleExpand(row.resource_id)}
                    >
                      {row.resource_id}
                    </TableCell>
                    <TableCell className="capitalize">{row.environment}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {row.waste_score.toFixed(1)}%
                    </TableCell>
                    <TableCell className="text-right">
                      <span className="font-mono font-medium text-red-400">{row.risk_score}</span>
                    </TableCell>
                    <TableCell>
                      <Badge variant={riskBadgeVariant(row.risk_level)}>
                        {formatRiskLevel(row.risk_level)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={recommendationBadgeVariant(row.recommendation)}>
                        {row.recommendation}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(row.monthly_cost)}
                    </TableCell>
                  </TableRow>
                  {isExpanded && (
                    <TableRow className="bg-muted/20 hover:bg-muted/20">
                      <TableCell colSpan={8} className="py-4">
                        <div className="space-y-3 px-2">
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                              Gemini Explanation
                            </p>
                            <p className="mt-1 text-sm leading-relaxed text-foreground">
                              {row.risk_explanation}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                            <span>
                              Business critical:{" "}
                              <strong className="text-foreground">
                                {row.business_critical ? "Yes" : "No"}
                              </strong>
                            </span>
                            <span>
                              Load balancer:{" "}
                              <strong className="text-foreground">
                                {row.attached_to_load_balancer ? "Yes" : "No"}
                              </strong>
                            </span>
                            <span>
                              Auto Scaling:{" "}
                              <strong className="text-foreground">
                                {row.member_of_autoscaling_group ? "Yes" : "No"}
                              </strong>
                            </span>
                            <span>
                              Owner:{" "}
                              <strong className="text-foreground">
                                {row.owner_exists ? "Yes" : "No"}
                              </strong>
                            </span>
                            <span>
                              Last activity:{" "}
                              <strong className="text-foreground">
                                {row.recent_activity_days} days ago
                              </strong>
                            </span>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{filtered.length} high-risk resource(s)</span>
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
