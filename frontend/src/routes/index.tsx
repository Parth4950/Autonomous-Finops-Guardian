import { createBrowserRouter } from "react-router-dom";
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

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
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
    ],
  },
]);
