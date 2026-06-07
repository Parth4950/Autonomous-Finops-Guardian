import { BarChart as TremorBarChart } from "@tremor/react";
import { formatCurrency } from "@/lib/utils";

interface SavingsByRecommendationChartProps {
  data: {
    category: string;
    annual: number;
    monthly: number;
    count: number;
  }[];
}

export function SavingsByRecommendationChart({ data }: SavingsByRecommendationChartProps) {
  const chartData = data.map((item) => ({
    category: item.category.length > 18 ? `${item.category.slice(0, 16)}…` : item.category,
    "Annual Savings": item.annual,
    "Monthly Savings": item.monthly,
  }));

  return (
    <TremorBarChart
      className="mt-2 h-72"
      data={chartData}
      index="category"
      categories={["Annual Savings", "Monthly Savings"]}
      colors={["emerald", "blue"]}
      valueFormatter={(v) => formatCurrency(v)}
      showAnimation
      yAxisWidth={56}
    />
  );
}
