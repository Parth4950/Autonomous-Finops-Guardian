"""Canonical data paths for agent outputs consumed by the API layer."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RESOURCES_CSV = PROJECT_ROOT / "synthetic_data" / "cloud_resources.csv"
WASTE_FORECAST_CSV = PROJECT_ROOT / "ml" / "forecasting" / "results" / "forecast_results.csv"
WASTE_PREDICTIONS_CSV = PROJECT_ROOT / "ml" / "isolation_forest" / "results" / "predictions.csv"
RISK_ASSESSMENT_CSV = PROJECT_ROOT / "agents" / "risk_assessor" / "results" / "risk_assessment.csv"
AUDIT_RESULTS_CSV = PROJECT_ROOT / "agents" / "auditor" / "results" / "audit_results.csv"
EXECUTIVE_REPORT_JSON = PROJECT_ROOT / "agents" / "auditor" / "results" / "executive_report.json"
REMEDIATION_PLAN_CSV = PROJECT_ROOT / "agents" / "planner" / "results" / "remediation_plan.csv"
APPROVALS_JSON = PROJECT_ROOT / "workflow" / "results" / "approvals.json"
EXECUTION_HISTORY_CSV = PROJECT_ROOT / "agents" / "executor" / "results" / "execution_history.csv"
ROLLBACK_PLANS_JSON = PROJECT_ROOT / "agents" / "executor" / "results" / "rollback_plans.json"
EXECUTION_LOGS_DIR = PROJECT_ROOT / "agents" / "executor" / "logs"
FORECAST_DASHBOARD_JSON = PROJECT_ROOT / "ml" / "forecasting" / "results" / "forecast_dashboard.json"
FORECAST_DASHBOARD_FALLBACK = PROJECT_ROOT / "frontend" / "src" / "data" / "forecast-predictions.json"
