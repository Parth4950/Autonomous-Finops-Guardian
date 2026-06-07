import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  EXECUTION_DATE_RANGE_LABELS,
  STATUS_LABELS,
  type ExecutionDateRange,
} from "@/lib/execution-transforms";
import { formatAction } from "@/lib/transforms";
import { Calendar, Download, Search } from "lucide-react";

interface ExecutionToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  actionFilter: string;
  onActionFilterChange: (value: string) => void;
  dateRange: ExecutionDateRange;
  onDateRangeChange: (value: ExecutionDateRange) => void;
  actions: string[];
  onDownloadAllLogs: () => void;
  recordCount: number;
}

export function ExecutionToolbar({
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  actionFilter,
  onActionFilterChange,
  dateRange,
  onDateRangeChange,
  actions,
  onDownloadAllLogs,
  recordCount,
}: ExecutionToolbarProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card/60 p-4 xl:flex-row xl:items-center xl:justify-between">
      <div className="flex flex-1 flex-wrap items-center gap-3">
        <div className="relative min-w-[200px] flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search executions..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>

        <Select value={statusFilter} onValueChange={onStatusFilterChange}>
          <SelectTrigger className="h-9 w-[140px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={actionFilter} onValueChange={onActionFilterChange}>
          <SelectTrigger className="h-9 w-[170px]">
            <SelectValue placeholder="Action" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Actions</SelectItem>
            {actions.map((action) => (
              <SelectItem key={action} value={action}>
                {formatAction(action)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <Select
            value={dateRange}
            onValueChange={(value) => onDateRangeChange(value as ExecutionDateRange)}
          >
            <SelectTrigger className="h-9 w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(EXECUTION_DATE_RANGE_LABELS) as ExecutionDateRange[]).map((key) => (
                <SelectItem key={key} value={key}>
                  {EXECUTION_DATE_RANGE_LABELS[key]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-xs text-muted-foreground">{recordCount} records</span>
        <Button variant="outline" size="sm" onClick={onDownloadAllLogs}>
          <Download className="mr-2 h-4 w-4" />
          Download Logs
        </Button>
      </div>
    </div>
  );
}
