import { cn } from "@/lib/utils";

export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-secondary/60", className)}
      style={style}
      aria-hidden="true"
    />
  );
}

interface SkeletonKpiGridProps {
  count?: number;
  columns?: 2 | 3 | 4;
}

export function SkeletonKpiGrid({ count = 4, columns = 4 }: SkeletonKpiGridProps) {
  const gridClass =
    columns === 2
      ? "sm:grid-cols-2"
      : columns === 3
        ? "sm:grid-cols-3"
        : "sm:grid-cols-2 xl:grid-cols-4";

  return (
    <div className={cn("grid gap-4", gridClass)}>
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="rounded-lg border border-border bg-card/40 p-5"
        >
          <Skeleton className="h-8 w-8 rounded-md" />
          <Skeleton className="mt-4 h-3 w-24" />
          <Skeleton className="mt-2 h-8 w-32" />
          <Skeleton className="mt-3 h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

interface SkeletonChartProps {
  height?: number;
}

export function SkeletonChart({ height = 280 }: SkeletonChartProps) {
  return (
    <div className="rounded-lg border border-border bg-card/40 p-5">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-2 h-3 w-56" />
      <Skeleton className="mt-6 w-full" style={{ height }} />
    </div>
  );
}

interface SkeletonTableProps {
  rows?: number;
  columns?: number;
}

export function SkeletonTable({ rows = 8, columns = 6 }: SkeletonTableProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="border-b border-border bg-secondary/30 px-4 py-3">
        <div className="flex gap-4">
          {Array.from({ length: columns }).map((_, index) => (
            <Skeleton key={index} className="h-4 flex-1" />
          ))}
        </div>
      </div>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-4 border-b border-border/50 px-4 py-3 last:border-0">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton key={colIndex} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonPage({ kpiCount = 4 }: { kpiCount?: number }) {
  return (
    <div className="space-y-6">
      <SkeletonKpiGrid count={kpiCount} />
      <div className="grid gap-4 lg:grid-cols-2">
        <SkeletonChart />
        <SkeletonChart />
      </div>
      <SkeletonTable />
    </div>
  );
}
