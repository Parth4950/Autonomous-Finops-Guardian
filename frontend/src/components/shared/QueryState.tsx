import { Button } from "@/components/ui/button";
import { SkeletonPage } from "@/components/shared/Skeletons";
import { cn } from "@/lib/utils";
import { AlertCircle, CloudOff, Inbox, Loader2 } from "lucide-react";

interface LoadingStateProps {
  message?: string;
  className?: string;
  variant?: "spinner" | "skeleton";
  skeleton?: React.ReactNode;
}

export function LoadingState({
  message = "Loading data...",
  className,
  variant = "spinner",
  skeleton,
}: LoadingStateProps) {
  if (variant === "skeleton") {
    return (
      <div className={cn("space-y-3", className)} aria-busy="true" aria-live="polite">
        {skeleton ?? <SkeletonPage />}
        <p className="sr-only">{message}</p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-border bg-card/40 px-6 py-16 text-center",
        className
      )}
      aria-busy="true"
    >
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  message = "Failed to load data from the API.",
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-lg border border-red-500/30 bg-red-500/5 px-6 py-16 text-center",
        className
      )}
      role="alert"
    >
      <div className="rounded-full border border-red-500/30 bg-red-500/10 p-3">
        <AlertCircle className="h-8 w-8 text-red-400" />
      </div>
      <div>
        <p className="text-sm font-medium text-red-200">Unable to reach FinOps API</p>
        <p className="mt-1 max-w-md text-sm text-red-300/90">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

interface EmptyStateProps {
  message?: string;
  className?: string;
}

export function EmptyState({
  message = "No records found.",
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border bg-card/20 px-6 py-16 text-center",
        className
      )}
    >
      <div className="rounded-full border border-border bg-secondary/40 p-3">
        <Inbox className="h-8 w-8 text-muted-foreground" />
      </div>
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

export function ApiDisconnectedState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-amber-500/30 bg-amber-500/5 px-6 py-16 text-center">
      <CloudOff className="h-10 w-10 text-amber-400" />
      <p className="text-sm text-amber-200">Backend unavailable — start FastAPI on port 8000</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry connection
        </Button>
      )}
    </div>
  );
}

interface QueryStateProps {
  isLoading: boolean;
  isError: boolean;
  error?: Error | null;
  isEmpty?: boolean;
  loadingMessage?: string;
  emptyMessage?: string;
  onRetry?: () => void;
  children?: React.ReactNode;
  className?: string;
  loadingVariant?: "spinner" | "skeleton";
  skeleton?: React.ReactNode;
}

export function QueryState({
  isLoading,
  isError,
  error,
  isEmpty = false,
  loadingMessage,
  emptyMessage,
  onRetry,
  children,
  className,
  loadingVariant = "skeleton",
  skeleton,
}: QueryStateProps) {
  if (isLoading) {
    return (
      <LoadingState
        message={loadingMessage}
        className={className}
        variant={loadingVariant}
        skeleton={skeleton}
      />
    );
  }
  if (isError) {
    return (
      <ErrorState
        message={error?.message ?? "Request failed"}
        onRetry={onRetry}
        className={className}
      />
    );
  }
  if (isEmpty) {
    return <EmptyState message={emptyMessage} className={className} />;
  }
  return <>{children}</>;
}
