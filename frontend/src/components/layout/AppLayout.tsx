import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";
import { cn } from "@/lib/utils";

const pageTitles: Record<string, string> = {
  "/": "Overview",
  "/resources": "Resources",
  "/anomalies": "Anomaly Detection",
  "/forecasting": "Forecasting",
  "/risk": "Risk Assessment",
  "/audit": "Audit Reports",
  "/plans": "Remediation Plans",
  "/approvals": "Approval Center",
  "/executions": "Execution History",
  "/settings": "Settings",
};

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const title = pageTitles[location.pathname] ?? "Dashboard";

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative z-50 h-full w-60">
            <Sidebar />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Navbar title={title} onMenuClick={() => setSidebarOpen(true)} />
        <main className={cn("flex-1 overflow-y-auto p-4 lg:p-6")}>
          <div className="mb-4 rounded-md border border-emerald-500/25 bg-emerald-500/5 px-4 py-2 text-xs text-emerald-700 dark:text-emerald-200" role="status">
            Workspace records are isolated to your account. Run a cloud scan to refresh your inventory, risk assessments, and remediation plans.
          </div>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
