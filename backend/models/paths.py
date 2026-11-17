"""Canonical data paths for agent outputs consumed by the API layer."""

from __future__ import annotations

import os
from uuid import UUID
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACES_ROOT = PROJECT_ROOT / "runtime" / "workspaces"


def scan_workspace_path(user_id: int, scan_id: str, *, root: Path | None = None) -> Path:
    """Return a safe, unique workspace path for one user-owned scan."""
    if user_id <= 0:
        raise ValueError("user_id must be a positive integer")
    normalized_scan_id = str(UUID(scan_id))
    return (root or DEFAULT_WORKSPACES_ROOT) / str(user_id) / normalized_scan_id


def workspace_path(project_path: Path) -> Path:
    """Map a project artifact path into FINOPS_WORKSPACE_DIR when configured.

    Standalone agent invocations without the variable keep their existing
    project-root defaults. Pipeline subprocesses receive a unique workspace
    and therefore resolve both inputs and outputs within that scan only.
    """
    workspace_dir = os.getenv("FINOPS_WORKSPACE_DIR")
    if not workspace_dir:
        return project_path
    project_relative = project_path.resolve().relative_to(PROJECT_ROOT.resolve())
    return Path(workspace_dir).resolve() / project_relative

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
