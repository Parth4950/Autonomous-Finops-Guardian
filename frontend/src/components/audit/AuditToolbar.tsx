import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AUDIT_DATE_RANGE_LABELS,
  type AuditDateRange,
} from "@/lib/audit-transforms";
import { Calendar, Download, FileText } from "lucide-react";

interface AuditToolbarProps {
  dateRange: AuditDateRange;
  onDateRangeChange: (range: AuditDateRange) => void;
  onExportCsv: () => void;
  onExportPdf: () => void;
  recordCount: number;
}

export function AuditToolbar({
  dateRange,
  onDateRangeChange,
  onExportCsv,
  onExportPdf,
  recordCount,
}: AuditToolbarProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card/60 p-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Calendar className="h-4 w-4" />
          <span>Report period</span>
        </div>
        <Select value={dateRange} onValueChange={(v) => onDateRangeChange(v as AuditDateRange)}>
          <SelectTrigger className="h-9 w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(AUDIT_DATE_RANGE_LABELS) as AuditDateRange[]).map((key) => (
              <SelectItem key={key} value={key}>
                {AUDIT_DATE_RANGE_LABELS[key]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-xs text-muted-foreground">{recordCount} resources audited</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={onExportCsv} className="h-9">
          <Download className="mr-2 h-4 w-4" />
          Download CSV
        </Button>
        <Button variant="outline" size="sm" onClick={onExportPdf} className="h-9">
          <FileText className="mr-2 h-4 w-4" />
          Export PDF
        </Button>
      </div>
    </div>
  );
}
