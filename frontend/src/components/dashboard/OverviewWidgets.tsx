import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Card as TremorCard, Metric, Text, BadgeDelta, Flex } from "@tremor/react";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/utils";

interface KpiCardProps {
  title: string;
  value: string;
  delta: number;
  deltaLabel: string;
  icon: React.ReactNode;
  accent?: "purple" | "green" | "blue" | "amber" | "red";
}

const accentStyles = {
  purple: "from-[#7745FF]/20 to-transparent border-[#7745FF]/30 text-[#9B7BFF]",
  green: "from-emerald-500/15 to-transparent border-emerald-500/30 text-emerald-400",
  blue: "from-blue-500/15 to-transparent border-blue-500/30 text-blue-400",
  amber: "from-amber-500/15 to-transparent border-amber-500/30 text-amber-400",
  red: "from-red-500/15 to-transparent border-red-500/30 text-red-400",
};

export function KpiCard({ title, value, delta, deltaLabel, icon, accent = "purple" }: KpiCardProps) {
  const isPositive = delta >= 0;
  const styles = accentStyles[accent];

  return (
    <TremorCard
      className={cn(
        "rounded-lg border bg-gradient-to-br bg-card p-0 ring-0 dark:bg-card",
        styles
      )}
      decoration="top"
      decorationColor={accent === "purple" ? "violet" : accent === "green" ? "emerald" : accent === "red" ? "red" : accent === "amber" ? "amber" : "blue"}
    >
      <div className="p-5">
        <Flex alignItems="start" justifyContent="between">
          <div className={cn("rounded-md border p-2", styles)}>
            {icon}
          </div>
          <BadgeDelta
            deltaType={isPositive ? "moderateIncrease" : "moderateDecrease"}
            isIncreasePositive={title !== "High Risk Resources"}
            size="xs"
          >
            {Math.abs(delta).toFixed(1)}%
          </BadgeDelta>
        </Flex>
        <Text className="mt-4 text-muted-foreground">{title}</Text>
        <Metric className="mt-1 text-foreground">{value}</Metric>
        <Flex justifyContent="start" alignItems="center" className="mt-2 gap-1">
          {isPositive ? (
            <ArrowUpRight className="h-3 w-3 text-muted-foreground" />
          ) : (
            <ArrowDownRight className="h-3 w-3 text-muted-foreground" />
          )}
          <Text className="text-xs text-muted-foreground">{deltaLabel}</Text>
        </Flex>
      </div>
    </TremorCard>
  );
}

export function ChartPanel({
  title,
  subtitle,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("panel overflow-hidden", className)}>
      <div className="border-b border-border px-5 py-4">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

export function ChartLegend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="mt-3 flex flex-wrap gap-4">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: item.color }} />
          {item.label}
        </div>
      ))}
    </div>
  );
}

export function formatKpiCurrency(value: number): string {
  return formatCurrency(value);
}
