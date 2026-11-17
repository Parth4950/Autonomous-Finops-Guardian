import { Bell, Menu, Search, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DataModeNotice } from "@/components/shared/DataModeNotice";
import { useHealth } from "@/hooks/useApiQueries";
import { useDataScanMode } from "@/hooks/useDataScanMode";
import { formatRelativeFromMs } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { useAuth } from "@/auth/AuthContext";
import { useNavigate } from "react-router-dom";

interface NavbarProps {
  onMenuClick?: () => void;
  title?: string;
}

export function Navbar({ onMenuClick, title = "Dashboard" }: NavbarProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { data, isError, isFetching, dataUpdatedAt, isLoading } = useHealth();
  const scanMode = useDataScanMode();

  const apiOnline = !isError && data?.status === "healthy";
  const statusLabel = isLoading
    ? "Checking API…"
    : isError
      ? "API offline"
      : isFetching
        ? "Syncing…"
        : "API connected";

  const lastChecked =
    dataUpdatedAt > 0 ? ` · checked ${formatRelativeFromMs(dataUpdatedAt)}` : "";

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card/50 px-4 backdrop-blur-sm lg:px-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenuClick}>
          <Menu className="h-5 w-5" />
        </Button>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-foreground">{title}</p>
            <DataModeNotice variant="inline" scanMode={scanMode} />
          </div>
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className={cn(
                "inline-block h-1.5 w-1.5 rounded-full",
                apiOnline ? "bg-emerald-400" : isLoading ? "bg-amber-400" : "bg-red-400"
              )}
            />
            {statusLabel}
            {lastChecked}
            <span className="hidden sm:inline"> · Simulation mode</span>
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="hidden items-center gap-2 rounded-md border border-border bg-background px-3 py-1.5 md:flex">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search resources..."
            className="w-48 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            disabled
            aria-disabled
            title="Search coming soon"
          />
          <kbd className="rounded border border-border px-1.5 text-[10px] text-muted-foreground opacity-50">
            ⌘K
          </kbd>
        </div>
        <Button
          variant="ghost"
          size="icon"
          title="Notification preferences"
          aria-label="Notification preferences"
          onClick={() => navigate("/settings?tab=notifications")}
        >
          <Bell className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          title="Settings"
          aria-label="Settings"
          onClick={() => navigate("/settings")}
        >
          <Settings className="h-4 w-4" />
        </Button>
        <Button variant="ghost" className="ml-1 h-9 gap-2 px-2" title={user?.email} onClick={() => { void logout().catch(() => undefined).finally(() => navigate("/login", { replace: true })); }}>
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-xs font-semibold text-primary">{(user?.full_name??"U").split(/\s+/).map(part=>part[0]).slice(0,2).join("").toUpperCase()}</span>
          <span className="hidden text-xs md:inline">Sign out</span>
        </Button>
      </div>
    </header>
  );
}
