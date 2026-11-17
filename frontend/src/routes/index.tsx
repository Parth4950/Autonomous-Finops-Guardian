import { createBrowserRouter, Navigate, RouterProvider, useLocation } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import OverviewPage from "@/pages/Overview";
import ResourcesPage from "@/pages/Resources";
import AnomaliesPage from "@/pages/Anomalies";
import ForecastingPage from "@/pages/Forecasting";
import RiskPage from "@/pages/Risk";
import AuditPage from "@/pages/Audit";
import PlansPage from "@/pages/Plans";
import ApprovalsPage from "@/pages/Approvals";
import ExecutionsPage from "@/pages/Executions";
import SettingsPage from "@/pages/Settings";
import LoginPage from "@/pages/Login";
import RegisterPage from "@/pages/Register";
import { AuthProvider, useAuth } from "@/auth/AuthContext";

function ProtectedApp() {
  const { user, isSimulationMode, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="grid min-h-screen place-items-center bg-background text-muted-foreground">Restoring session…</div>;
  if (!user && !isSimulationMode) return <Navigate to="/login" replace state={{ from: location }} />;
  return <AppLayout />;
}

const routes = [
  {path:"/login",element:<LoginPage/>},
  {path:"/register",element:<RegisterPage/>},
  {
    path: "/",
    element: <ProtectedApp />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: "resources", element: <ResourcesPage /> },
      { path: "anomalies", element: <AnomaliesPage /> },
      { path: "forecasting", element: <ForecastingPage /> },
      { path: "risk", element: <RiskPage /> },
      { path: "audit", element: <AuditPage /> },
      { path: "plans", element: <PlansPage /> },
      { path: "approvals", element: <ApprovalsPage /> },
      { path: "executions", element: <ExecutionsPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);

export function AppRoutes() { return <AuthProvider><RouterProvider router={router}/></AuthProvider>; }
