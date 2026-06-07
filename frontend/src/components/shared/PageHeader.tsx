import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  children?: React.ReactNode;
}

export function PageHeader({ title, description, children }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children && <div className="flex shrink-0 items-center gap-2">{children}</div>}
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function MetricCard({ label, value, subtext, trend, className }: MetricCardProps) {
  return (
    <div className={cn("panel p-5", className)}>
      <p className="metric-label">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
      {subtext && (
        <p
          className={cn(
            "mt-1 text-xs",
            trend === "up" && "text-emerald-400",
            trend === "down" && "text-red-400",
            !trend && "text-muted-foreground"
          )}
        >
          {subtext}
        </p>
      )}
    </div>
  );
}

interface StatusDotProps {
  status: "success" | "warning" | "error" | "info" | "neutral";
}

export function StatusDot({ status }: StatusDotProps) {
  const colors = {
    success: "bg-emerald-400",
    warning: "bg-amber-400",
    error: "bg-red-400",
    info: "bg-blue-400",
    neutral: "bg-muted-foreground",
  };
  return <span className={cn("inline-block h-2 w-2 rounded-full", colors[status])} />;
}
