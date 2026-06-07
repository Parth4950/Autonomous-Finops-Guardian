import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ActivityEvent } from "@/lib/execution-transforms";
import { executionStatusBadgeVariant, STATUS_LABELS } from "@/lib/execution-transforms";
import { formatTimestamp } from "@/lib/transforms";
import { Activity, AlertCircle, CheckCircle2, RotateCcw } from "lucide-react";

interface ExecutionActivityFeedProps {
  events: ActivityEvent[];
  limit?: number;
}

const TYPE_ICONS = {
  info: Activity,
  success: CheckCircle2,
  error: AlertCircle,
  rollback: RotateCcw,
} as const;

const TYPE_COLORS = {
  info: "text-blue-400",
  success: "text-emerald-400",
  error: "text-red-400",
  rollback: "text-amber-400",
} as const;

export function ExecutionActivityFeed({ events, limit = 12 }: ExecutionActivityFeedProps) {
  const visible = events.slice(0, limit);

  return (
    <Card className="border-border bg-card/60">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Activity Feed</CardTitle>
        <p className="text-xs text-muted-foreground">
          Recent execution events across all resources
        </p>
      </CardHeader>
      <CardContent>
        {visible.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No execution activity recorded yet.
          </p>
        ) : (
          <ul className="space-y-3">
            {visible.map((event) => {
              const Icon = TYPE_ICONS[event.type];
              const color = TYPE_COLORS[event.type];

              return (
                <li
                  key={event.id}
                  className="flex items-start gap-3 rounded-md border border-border/60 bg-secondary/20 px-3 py-2.5"
                >
                  <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${color}`} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{event.message}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {event.resource_id}
                      </span>
                      <Badge
                        variant={executionStatusBadgeVariant(event.status)}
                        className="text-[10px]"
                      >
                        {STATUS_LABELS[event.status as keyof typeof STATUS_LABELS] ??
                          event.status}
                      </Badge>
                      <span className="text-[10px] text-muted-foreground">
                        {formatTimestamp(event.timestamp)}
                      </span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
