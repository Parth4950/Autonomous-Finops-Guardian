import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  formatStatus,
  formatTimestamp,
  historyStatusVariant,
} from "@/lib/transforms";
import { cn } from "@/lib/utils";
import { ArrowRight, History, Search } from "lucide-react";

export interface ApprovalHistoryEvent {
  approval_id: string;
  resource_id: string;
  previous_status: string | null;
  new_status: string;
  timestamp: string;
  actor: string;
  notes: string | null;
}

interface ApprovalHistoryTimelineProps {
  events: ApprovalHistoryEvent[];
}

const PAGE_SIZE = 12;

export function ApprovalHistoryTimeline({ events }: ApprovalHistoryTimelineProps) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!search) return events;
    const query = search.toLowerCase();
    return events.filter(
      (event) =>
        event.resource_id.toLowerCase().includes(query) ||
        event.actor.toLowerCase().includes(query) ||
        event.approval_id.toLowerCase().includes(query) ||
        (event.notes?.toLowerCase().includes(query) ?? false)
    );
  }, [events, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageData = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  return (
    <div className="space-y-4">
      <div className="relative sm:max-w-xs">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search audit trail..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          className="pl-9"
        />
      </div>

      <div className="relative space-y-0">
        <div className="absolute bottom-2 left-[11px] top-2 w-px bg-border" />

        {pageData.map((event, index) => (
          <div
            key={`${event.approval_id}-${event.timestamp}-${index}`}
            className="relative flex gap-4 pb-6 last:pb-0"
          >
            <div className="relative z-10 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-card">
              <History className="h-3 w-3 text-muted-foreground" />
            </div>

            <div className="min-w-0 flex-1 rounded-lg border border-border bg-card/60 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-medium">{event.resource_id}</span>
                <span className="text-muted-foreground">·</span>
                <span className="text-xs text-muted-foreground">{formatTimestamp(event.timestamp)}</span>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                {event.previous_status ? (
                  <>
                    <Badge variant={historyStatusVariant(event.previous_status)}>
                      {formatStatus(event.previous_status)}
                    </Badge>
                    <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  </>
                ) : (
                  <span className="text-xs text-muted-foreground">Created →</span>
                )}
                <Badge variant={historyStatusVariant(event.new_status)}>
                  {formatStatus(event.new_status)}
                </Badge>
              </div>

              <p className="mt-2 text-xs text-muted-foreground">
                Actor: <span className="text-foreground">{event.actor}</span>
              </p>
              {event.notes && (
                <p className={cn("mt-1 text-xs leading-relaxed text-muted-foreground")}>
                  {event.notes}
                </p>
              )}
            </div>
          </div>
        ))}

        {pageData.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">No audit events found.</p>
        )}
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{filtered.length} audit event(s)</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="rounded border border-border px-2 py-1 disabled:opacity-40"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            Prev
          </button>
          <span>
            Page {page + 1} / {totalPages}
          </span>
          <button
            type="button"
            className="rounded border border-border px-2 py-1 disabled:opacity-40"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
