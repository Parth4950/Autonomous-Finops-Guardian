import { Badge } from "@/components/ui/badge";
import { formatStatus, statusBadgeVariant, type ApprovalStatus } from "@/lib/transforms";

interface ApprovalStatusBadgeProps {
  status: ApprovalStatus | string;
  className?: string;
}

export function ApprovalStatusBadge({ status, className }: ApprovalStatusBadgeProps) {
  return (
    <Badge variant={statusBadgeVariant(status)} className={className}>
      {formatStatus(status)}
    </Badge>
  );
}
