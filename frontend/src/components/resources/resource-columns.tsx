import { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/badge";
import { DataTableColumnHeader } from "@/components/ui/data-table-column-header";
import type { EnrichedResource } from "@/lib/api/types";
import { formatCurrency } from "@/lib/utils";

function envVariant(env: string | null) {
  if (env === "production") return "destructive" as const;
  if (env === "staging") return "warning" as const;
  return "secondary" as const;
}

function labelVariant(label: string) {
  if (label === "idle" || label === "anomaly") return "destructive" as const;
  if (label === "normal") return "success" as const;
  return "outline" as const;
}

export const resourceColumns: ColumnDef<EnrichedResource>[] = [
  {
    accessorKey: "resource_id",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Resource ID" />,
    cell: ({ row }) => (
      <span className="font-mono text-xs text-foreground">{row.getValue("resource_id")}</span>
    ),
  },
  {
    accessorKey: "resource_label",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Label" />,
    cell: ({ row }) => {
      const label = row.getValue("resource_label") as string;
      return (
        <Badge variant={labelVariant(label)} className="capitalize">
          {label}
        </Badge>
      );
    },
    filterFn: (row, id, value) => value === "all" || row.getValue(id) === value,
  },
  {
    accessorKey: "monthly_cost",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Monthly Cost" className="justify-end" />
    ),
    cell: ({ row }) => (
      <div className="text-right font-mono tabular-nums">
        {formatCurrency(row.getValue("monthly_cost"))}
      </div>
    ),
  },
  {
    accessorKey: "avg_cpu",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Avg CPU" className="justify-end" />
    ),
    cell: ({ row }) => (
      <div className="text-right tabular-nums">{Number(row.getValue("avg_cpu")).toFixed(1)}%</div>
    ),
  },
  {
    accessorKey: "waste_score",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Waste Score" className="justify-end" />
    ),
    cell: ({ row }) => {
      const value = row.getValue("waste_score") as number | null;
      return (
        <div className="text-right tabular-nums">
          {value != null ? `${value.toFixed(1)}%` : "—"}
        </div>
      );
    },
  },
  {
    accessorKey: "risk_score",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Risk Score" className="justify-end" />
    ),
    cell: ({ row }) => {
      const value = row.getValue("risk_score") as number | null;
      return <div className="text-right tabular-nums">{value ?? "—"}</div>;
    },
  },
  {
    accessorKey: "environment",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Environment" />,
    cell: ({ row }) => {
      const env = row.getValue("environment") as string | null;
      if (!env) return <span className="text-muted-foreground">—</span>;
      return <Badge variant={envVariant(env)}>{env}</Badge>;
    },
    filterFn: (row, id, value) => value === "all" || row.getValue(id) === value,
  },
];

export const defaultHiddenColumns = {};

export type SortField = "monthly_cost" | "waste_score" | "risk_score" | "avg_cpu";

export function sortFieldToState(field: SortField, desc = true) {
  return [{ id: field, desc }];
}

export const labelOptions = ["normal", "idle", "anomaly"];
export const environmentOptions = ["production", "staging", "development"];
