import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckSquare,
  Cloud,
  History,
  LayoutDashboard,
  LineChart,
  Play,
  Shield,
  TrendingDown,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/resources", label: "Resources", icon: Cloud },
  { to: "/anomalies", label: "Anomaly Detection", icon: AlertTriangle },
  { to: "/forecasting", label: "Forecasting", icon: LineChart },
  { to: "/risk", label: "Risk Assessment", icon: Shield },
  { to: "/audit", label: "Audit Reports", icon: BarChart3 },
  { to: "/plans", label: "Remediation Plans", icon: TrendingDown },
  { to: "/approvals", label: "Approval Center", icon: CheckSquare },
  { to: "/executions", label: "Execution History", icon: History },
];

interface SidebarProps {
  collapsed?: boolean;
}

export function Sidebar({ collapsed = false }: SidebarProps) {
  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-sidebar-border bg-sidebar transition-all duration-200",
        collapsed ? "w-16" : "w-60"
      )}
    >
      <div className="flex h-14 items-center gap-2.5 border-b border-sidebar-border px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary">
          <Activity className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-sidebar-foreground">FinOps Guardian</p>
            <p className="truncate text-[10px] text-muted-foreground">Autonomous Platform</p>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/15 text-primary"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      {!collapsed && (
        <div className="border-t border-sidebar-border p-4">
          <div className="flex items-center gap-2 rounded-md bg-sidebar-accent px-3 py-2">
            <Play className="h-3.5 w-3.5 text-emerald-400" />
            <div>
              <p className="text-xs font-medium text-sidebar-foreground">Pipeline Active</p>
              <p className="text-[10px] text-muted-foreground">Simulation mode</p>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
