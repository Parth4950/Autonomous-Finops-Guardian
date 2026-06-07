import { Fragment, useMemo, useState } from "react";
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
import {
  ACTION_LABELS,
  PLAN_ACTIONS,
  actionBadgeVariant,
  filterPlans,
  formatPlanAction,
  parseExecutionSteps,
  type EnrichedPlan,
  type SavingsSort,
} from "@/lib/plan-transforms";
import { riskBadgeVariant } from "@/lib/transforms";
import { formatCurrency } from "@/lib/utils";
import { ChevronDown, ChevronRight, ExternalLink, Search } from "lucide-react";

interface RemediationPlansTableProps {
  data: EnrichedPlan[];
  onOpenDetail: (plan: EnrichedPlan) => void;
}

export function RemediationPlansTable({ data, onOpenDetail }: RemediationPlansTableProps) {
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [sort, setSort] = useState<SavingsSort>("desc");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = useMemo(
    () => filterPlans(data, search, actionFilter, riskFilter, sort),
    [data, search, actionFilter, riskFilter, sort]
  );

  function toggleExpanded(resourceId: string) {
    setExpandedId((current) => (current === resourceId ? null : resourceId));
  }

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

        <Select value={actionFilter} onValueChange={setActionFilter}>
          <SelectTrigger className="h-9 w-[180px]">
            <SelectValue placeholder="Action" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Actions</SelectItem>
            {PLAN_ACTIONS.map((action) => (
              <SelectItem key={action} value={action}>
                {ACTION_LABELS[action]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

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

        <Select value={sort} onValueChange={(value) => setSort(value as SavingsSort)}>
          <SelectTrigger className="h-9 w-[170px]">
            <SelectValue placeholder="Sort" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="desc">Savings: High → Low</SelectItem>
            <SelectItem value="asc">Savings: Low → High</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow className="bg-secondary/40 hover:bg-secondary/40">
              <TableHead className="w-8" />
              <TableHead>Resource ID</TableHead>
              <TableHead>Resource Type</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Risk Level</TableHead>
              <TableHead className="text-right">Estimated Savings</TableHead>
              <TableHead className="text-right">Waste Score</TableHead>
              <TableHead>Recommendation</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((plan) => {
              const expanded = expandedId === plan.resource_id;
              const steps = parseExecutionSteps(plan.execution_steps);

              return (
                <Fragment key={plan.resource_id}>
                  <TableRow
                    className="cursor-pointer"
                    onClick={() => toggleExpanded(plan.resource_id)}
                  >
                    <TableCell className="text-muted-foreground">
                      {expanded ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{plan.resource_id}</TableCell>
                    <TableCell className="capitalize text-sm">{plan.resource_type}</TableCell>
                    <TableCell>
                      <Badge variant={actionBadgeVariant(plan.action)}>
                        {formatPlanAction(plan.action)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={riskBadgeVariant(plan.risk_level)} className="capitalize">
                        {plan.risk_level}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-semibold tabular-nums text-emerald-400">
                      {formatCurrency(plan.estimated_savings)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {plan.waste_score.toFixed(1)}%
                    </TableCell>
                    <TableCell className="max-w-[180px] truncate text-xs text-muted-foreground">
                      {plan.recommendation}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenDetail(plan);
                        }}
                        aria-label="Open action detail"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>

                  {expanded && (
                    <TableRow className="bg-secondary/20 hover:bg-secondary/20">
                      <TableCell colSpan={9} className="p-0">
                        <div className="grid gap-4 border-t border-border p-5 md:grid-cols-2">
                          <DetailBlock title="Business Justification" text={plan.business_justification} />
                          <DetailBlock title="Technical Justification" text={plan.technical_justification} />
                          <DetailBlock title="Expected Outcome" text={plan.expected_outcome} />
                          <div>
                            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                              Execution Steps
                            </p>
                            <ol className="space-y-1.5">
                              {steps.map((step, index) => (
                                <li key={step} className="flex gap-2 text-sm text-foreground/90">
                                  <span className="font-mono text-xs text-muted-foreground">
                                    {index + 1}.
                                  </span>
                                  {step}
                                </li>
                              ))}
                            </ol>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}

            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} className="py-12 text-center text-muted-foreground">
                  No remediation plans match the current filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <p className="text-xs text-muted-foreground">
        Showing {filtered.length} of {data.length} remediation plans · sorted by estimated savings
      </p>
    </div>
  );
}

function DetailBlock({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      <p className="text-sm leading-relaxed text-foreground/90">{text}</p>
    </div>
  );
}
