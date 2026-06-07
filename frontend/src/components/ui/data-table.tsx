import * as React from "react";
import {
  ColumnDef,
  ColumnFiltersState,
  SortingState,
  VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataTablePagination } from "@/components/ui/data-table-pagination";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  sorting?: SortingState;
  onSortingChange?: React.Dispatch<React.SetStateAction<SortingState>>;
  columnFilters?: ColumnFiltersState;
  onColumnFiltersChange?: React.Dispatch<React.SetStateAction<ColumnFiltersState>>;
  globalFilter?: string;
  onGlobalFilterChange?: (value: string) => void;
  columnVisibility?: VisibilityState;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  sorting: controlledSorting,
  onSortingChange,
  columnFilters: controlledColumnFilters,
  onColumnFiltersChange,
  globalFilter: controlledGlobalFilter,
  onGlobalFilterChange,
  columnVisibility = {},
}: DataTableProps<TData, TValue>) {
  const [internalSorting, setInternalSorting] = React.useState<SortingState>([]);
  const [internalFilters, setInternalFilters] = React.useState<ColumnFiltersState>([]);
  const [internalGlobalFilter, setInternalGlobalFilter] = React.useState("");

  const sorting = controlledSorting ?? internalSorting;
  const setSorting = onSortingChange ?? setInternalSorting;
  const columnFilters = controlledColumnFilters ?? internalFilters;
  const setColumnFilters = onColumnFiltersChange ?? setInternalFilters;
  const globalFilter = controlledGlobalFilter ?? internalGlobalFilter;
  const setGlobalFilter = onGlobalFilterChange ?? setInternalGlobalFilter;

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnFilters,
      globalFilter,
      columnVisibility,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    globalFilterFn: "includesString",
    initialState: {
      pagination: { pageSize: 10 },
    },
  });

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  No resources match your filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <DataTablePagination table={table} />
    </div>
  );
}
