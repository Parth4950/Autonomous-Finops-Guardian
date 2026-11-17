import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { FlaskConical, LogIn, UserPlus } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";
import { Button } from "@/components/ui/button";
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
  const { isSimulationMode, exitSimulationMode } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
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
          {isSimulationMode ? (
            <div
              className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-primary/30 bg-primary/10 px-4 py-2.5 text-xs text-foreground"
              role="status"
            >
              <div className="flex items-center gap-2">
                <FlaskConical className="h-4 w-4 shrink-0 text-primary" />
                <span>
                  <strong>Simulation Mode (Demo Sandbox):</strong> You are exploring isolated
                  synthetic cloud data. Sign in or create an account for a private workspace and
                  live AWS scanning.
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 gap-1.5 text-xs"
                  onClick={() => {
                    exitSimulationMode();
                    navigate("/login");
                  }}
                >
                  <LogIn className="h-3.5 w-3.5" />
                  Sign In
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="default"
                  className="h-7 gap-1.5 text-xs"
                  onClick={() => {
                    exitSimulationMode();
                    navigate("/register");
                  }}
                >
                  <UserPlus className="h-3.5 w-3.5" />
                  Create Account
                </Button>
              </div>
            </div>
          ) : (
            <div
              className="mb-4 rounded-md border border-emerald-500/25 bg-emerald-500/5 px-4 py-2 text-xs text-emerald-700 dark:text-emerald-200"
              role="status"
            >
              Workspace records are isolated to your account. Run a cloud scan to refresh your
              inventory, risk assessments, and remediation plans.
            </div>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
