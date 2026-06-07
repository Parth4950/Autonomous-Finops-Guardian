import { useMemo, useState } from "react";
import { ColumnFiltersState, SortingState } from "@tanstack/react-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { ResourceTableToolbar } from "@/components/resources/ResourceTableToolbar";
import {
  defaultHiddenColumns,
  resourceColumns,
  sortFieldToState,
  type SortField,
} from "@/components/resources/resource-columns";
import { MetricCard, PageHeader } from "@/components/shared/PageHeader";
import { QueryState } from "@/components/shared/QueryState";
import { useEnrichedResourcesQuery } from "@/hooks/useApiQueries";
import { formatCurrency } from "@/lib/utils";

export default function ResourcesPage() {
  const { data = [], isLoading, isError, error, refetch } = useEnrichedResourcesQuery();
  const [globalFilter, setGlobalFilter] = useState("");
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [sortField, setSortField] = useState<SortField>("monthly_cost");
  const [sorting, setSorting] = useState<SortingState>(sortFieldToState("monthly_cost"));

  const stats = useMemo(() => {
    const zombies = data.filter((item) => (item.waste_score ?? 0) >= 85).length;
    const totalCost = data.reduce((sum, item) => sum + item.monthly_cost, 0);
    const withRisk = data.filter((item) => item.risk_score != null).length;
    return { total: data.length, zombies, totalCost, withRisk };
  }, [data]);

  const handleSortFieldChange = (field: SortField) => {
    setSortField(field);
    setSorting(sortFieldToState(field));
  };

  const handleReset = () => {
    setGlobalFilter("");
    setColumnFilters([]);
    setSortField("monthly_cost");
    setSorting(sortFieldToState("monthly_cost"));
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Resources"
        description="Scout Agent inventory — search, filter, and sort cloud resources"
      />

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => void refetch()}
        loadingMessage="Loading resource inventory..."
      >
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Total Resources" value={stats.total} subtext="From /resources API" />
            <MetricCard label="Zombie Candidates" value={stats.zombies} subtext="Waste score ≥ 85" />
            <MetricCard label="Monthly Spend" value={formatCurrency(stats.totalCost)} />
            <MetricCard label="Risk-Assessed" value={stats.withRisk} subtext="Merged from /risk" />
          </div>

          <Card>
            <CardHeader className="pb-4">
              <CardTitle>Resource Inventory</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {data.length === 0 ? (
                <QueryState isLoading={false} isError={false} isEmpty emptyMessage="No resources returned from the API." />
              ) : (
                <>
                  <ResourceTableToolbar
                    globalFilter={globalFilter}
                    onGlobalFilterChange={setGlobalFilter}
                    columnFilters={columnFilters}
                    onColumnFiltersChange={setColumnFilters}
                    sortField={sortField}
                    onSortFieldChange={handleSortFieldChange}
                    onReset={handleReset}
                  />
                  <DataTable
                    columns={resourceColumns}
                    data={data}
                    sorting={sorting}
                    onSortingChange={setSorting}
                    columnFilters={columnFilters}
                    onColumnFiltersChange={setColumnFilters}
                    globalFilter={globalFilter}
                    onGlobalFilterChange={setGlobalFilter}
                    columnVisibility={defaultHiddenColumns}
                  />
                </>
              )}
            </CardContent>
          </Card>
        </>
      </QueryState>
    </div>
  );
}
