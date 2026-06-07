import { ColumnFiltersState } from "@tanstack/react-table";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SortField } from "@/components/resources/resource-columns";
import { environmentOptions, labelOptions } from "@/components/resources/resource-columns";

interface ResourceTableToolbarProps {
  globalFilter: string;
  onGlobalFilterChange: (value: string) => void;
  columnFilters: ColumnFiltersState;
  onColumnFiltersChange: (filters: ColumnFiltersState) => void;
  sortField: SortField;
  onSortFieldChange: (field: SortField) => void;
  onReset: () => void;
}

export function ResourceTableToolbar({
  globalFilter,
  onGlobalFilterChange,
  columnFilters,
  onColumnFiltersChange,
  sortField,
  onSortFieldChange,
  onReset,
}: ResourceTableToolbarProps) {
  const labelFilter =
    (columnFilters.find((f) => f.id === "resource_label")?.value as string) ?? "all";
  const envFilter =
    (columnFilters.find((f) => f.id === "environment")?.value as string) ?? "all";

  const setFilter = (id: string, value: string) => {
    const rest = columnFilters.filter((f) => f.id !== id);
    if (value === "all") {
      onColumnFiltersChange(rest);
    } else {
      onColumnFiltersChange([...rest, { id, value }]);
    }
  };

  const hasFilters = globalFilter.length > 0 || labelFilter !== "all" || envFilter !== "all";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full lg:max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by resource ID..."
            value={globalFilter}
            onChange={(e) => onGlobalFilterChange(e.target.value)}
            className="pl-9"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <SlidersHorizontal className="hidden h-4 w-4 text-muted-foreground sm:block" />
          <Select value={sortField} onValueChange={(v) => onSortFieldChange(v as SortField)}>
            <SelectTrigger className="h-9 w-[160px]">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="monthly_cost">Sort: Monthly Cost</SelectItem>
              <SelectItem value="waste_score">Sort: Waste Score</SelectItem>
              <SelectItem value="risk_score">Sort: Risk Score</SelectItem>
              <SelectItem value="avg_cpu">Sort: Avg CPU</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={labelFilter} onValueChange={(v) => setFilter("resource_label", v)}>
          <SelectTrigger className="h-8 w-[130px]">
            <SelectValue placeholder="Label" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Labels</SelectItem>
            {labelOptions.map((label) => (
              <SelectItem key={label} value={label}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={envFilter} onValueChange={(v) => setFilter("environment", v)}>
          <SelectTrigger className="h-8 w-[150px]">
            <SelectValue placeholder="Environment" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Environments</SelectItem>
            {environmentOptions.map((env) => (
              <SelectItem key={env} value={env}>
                {env}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={onReset} className="h-8 px-2 text-muted-foreground">
            <X className="mr-1 h-4 w-4" />
            Reset
          </Button>
        )}
      </div>
    </div>
  );
}
