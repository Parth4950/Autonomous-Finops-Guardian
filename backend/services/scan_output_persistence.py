"""Persist a completed scan's private workspace outputs as owned records."""

from __future__ import annotations

import csv
import json
import math
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.finops import (
    Anomaly,
    Approval,
    ApprovalEvent,
    FinOpsReport,
    Forecast,
    Resource,
    Scan,
    ScanResourceSnapshot,
)
from workflow.models import ACTIONS_REQUIRING_APPROVAL


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _boolean(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _resource_type(external_id: str) -> str:
    lowered = external_id.lower()
    if lowered.startswith("vol-"):
        return "ebs_volume"
    if lowered.startswith("i-"):
        return "ec2_instance"
    if "volume" in lowered:
        return "ebs_volume"
    if "instance" in lowered:
        return "ec2_instance"
    return "cloud_resource"


def _upsert_report(db: Session, user_id: int, scan_id: str, report_type: str, data: Any, source: str) -> None:
    existing = db.scalar(select(FinOpsReport).where(
        FinOpsReport.user_id == user_id,
        FinOpsReport.scan_id == scan_id,
        FinOpsReport.report_type == report_type,
    ))
    payload = data if isinstance(data, dict) else {"items": data}
    if existing:
        existing.report_data = payload
        existing.source = source
    else:
        db.add(FinOpsReport(user_id=user_id, scan_id=scan_id, report_type=report_type, source=source, report_data=payload))


def persist_scan_outputs(db: Session, *, user_id: int, scan_id: str, workspace: Path) -> None:
    """Normalize agent artifacts into rows owned by the scan's user and scan."""
    scan = db.scalar(select(Scan).where(Scan.scan_id == scan_id, Scan.user_id == user_id))
    if scan is None:
        raise LookupError("Scan owner was not found")

    inventory_path = workspace / "synthetic_data" / "cloud_resources.csv"
    resource_rows = _read_csv(inventory_path)
    metadata_rows = _read_csv(workspace / "agents" / "scout" / "results" / "infrastructure_metadata.csv")
    metadata_by_id = {row.get("resource_id", ""): row for row in metadata_rows}
    source = _read_json(workspace / "synthetic_data" / "scan_source.json") or {}
    if source:
        _upsert_report(db, user_id, scan_id, "scan_source", source, "scout" if scan.mode == "aws" else "synthetic_generator")
    default_region = "ap-south-1" if scan.mode == "aws" else "synthetic"
    default_account_id = "aws" if scan.mode == "aws" else "synthetic"
    region = str(source.get("region") or default_region).strip() or default_region
    account_id = str(source.get("account_id") or default_account_id).strip() or default_account_id
    provider = "aws" if scan.mode == "aws" else "synthetic"
    snapshots_by_external: dict[str, ScanResourceSnapshot] = {}

    for row in resource_rows:
        external_id = str(row.get("resource_id") or "").strip()
        if not external_id:
            continue
        identity = select(Resource).where(
            Resource.user_id == user_id,
            Resource.provider == provider,
            Resource.account_id == account_id,
            Resource.region == region,
            Resource.external_id == external_id,
        )
        resource = db.scalar(identity)
        attributes = dict(row)
        attributes.update(metadata_by_id.get(external_id, {}))
        if resource is None:
            resource = Resource(
                user_id=user_id, provider=provider, account_id=account_id, region=region,
                external_id=external_id, resource_type=_resource_type(external_id), attributes=attributes,
            )
            db.add(resource)
            db.flush()
        else:
            resource.attributes = attributes
        snapshot = ScanResourceSnapshot(
            user_id=user_id, scan_id=scan_id, resource_id=resource.resource_id,
            estimated_monthly_cost=_number(row.get("monthly_cost")),
            avg_cpu=_number(row.get("avg_cpu")),
            avg_network_in=_number(row.get("avg_network_in")),
            avg_network_out=_number(row.get("avg_network_out")),
            resource_label=row.get("resource_label") or None,
            attributes=attributes,
        )
        db.add(snapshot)
        db.flush()
        snapshots_by_external[external_id] = snapshot

    prediction_path = workspace / "ml" / "isolation_forest" / "results" / "predictions.csv"
    prediction_rows = _read_csv(prediction_path)
    for row in prediction_rows:
        snapshot = snapshots_by_external.get(str(row.get("resource_id", "")))
        if snapshot:
            db.add(Anomaly(
                user_id=user_id, scan_id=scan_id, snapshot_id=snapshot.snapshot_id,
                prediction=_integer(row.get("prediction")), anomaly_score=_number(row.get("anomaly_score")),
                prediction_label=row.get("prediction_label") or None, result_data=dict(row),
            ))
    if prediction_path.is_file():
        _upsert_report(db, user_id, scan_id, "anomalies", prediction_rows, "isolation_forest")

    forecast_path = workspace / "ml" / "forecasting" / "results" / "forecast_results.csv"
    forecast_rows = _read_csv(forecast_path)
    chart_data = _read_json(workspace / "ml" / "forecasting" / "results" / "forecast_series_cache.json") or {}
    for row in forecast_rows:
        snapshot = snapshots_by_external.get(str(row.get("resource_id", "")))
        if snapshot:
            db.add(Forecast(
                user_id=user_id, scan_id=scan_id, snapshot_id=snapshot.snapshot_id,
                utilization_category=row.get("utilization_category") or None,
                waste_probability=row.get("waste_probability") or None,
                summary_data=dict(row), series_data=chart_data.get(str(row.get("resource_id", "")), {}),
            ))
    if forecast_path.is_file():
        _upsert_report(db, user_id, scan_id, "forecast_results", forecast_rows, "prophet")

    if inventory_path.is_file():
        _upsert_report(db, user_id, scan_id, "resources", resource_rows, "scout")

    reports = (
        ("risk_assessments", _read_csv(workspace / "agents" / "risk_assessor" / "results" / "risk_assessment.csv"), "risk_assessor"),
        ("audit_results", _read_csv(workspace / "agents" / "auditor" / "results" / "audit_results.csv"), "auditor"),
        ("plans", _read_csv(workspace / "agents" / "planner" / "results" / "remediation_plan.csv"), "planner"),
    )
    for report_type, rows, report_source in reports:
        artifact = {
            "risk_assessments": workspace / "agents" / "risk_assessor" / "results" / "risk_assessment.csv",
            "audit_results": workspace / "agents" / "auditor" / "results" / "audit_results.csv",
            "plans": workspace / "agents" / "planner" / "results" / "remediation_plan.csv",
        }[report_type]
        if artifact.is_file():
            _upsert_report(db, user_id, scan_id, report_type, rows, report_source)

    dashboard = _read_json(workspace / "ml" / "forecasting" / "results" / "forecast_dashboard.json")
    if dashboard is not None:
        _upsert_report(db, user_id, scan_id, "forecast_dashboard", dashboard, "forecast_export")
    executive = _read_json(workspace / "agents" / "auditor" / "results" / "executive_report.json")
    if executive is not None:
        _upsert_report(db, user_id, scan_id, "executive_report", executive, "auditor")

    packages = _read_json(workspace / "agents" / "planner" / "results" / "approval_packages.json") or []
    if not isinstance(packages, list):
        raise ValueError("Planner approval packages must be a JSON list")
    for package in packages:
        external_id = str(package.get("resource_id", ""))
        snapshot = snapshots_by_external.get(external_id)
        action = str(package.get("action", ""))
        if snapshot is None or action not in ACTIONS_REQUIRING_APPROVAL:
            continue
        approval_id = str(uuid.uuid5(uuid.UUID(scan_id), f"{external_id}:{action}"))
        if db.get(Approval, approval_id):
            continue
        approval = Approval(
            approval_id=approval_id, user_id=user_id, scan_id=scan_id,
            snapshot_id=snapshot.snapshot_id, action=action, status="pending",
            risk_level=str(package.get("risk_level") or "unknown"),
            estimated_savings=_number(package.get("estimated_savings")) or 0.0,
            business_justification=str(package.get("business_justification") or ""),
            execution_steps=[str(step) for step in package.get("execution_steps", [])],
        )
        db.add(approval)
        db.flush()
        db.add(ApprovalEvent(
            user_id=user_id, scan_id=scan_id, approval_id=approval_id,
            new_status="pending", notes="Created from scan planner output.",
        ))

