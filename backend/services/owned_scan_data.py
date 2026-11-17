"""Read helpers for authenticated users' completed scan records."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.finops import FinOpsReport, Scan, ScanResourceSnapshot
from backend.services.data_loader import DataNotFoundError


def latest_completed_scan(db: Session, user_id: int) -> Scan:
    scan = db.scalar(
        select(Scan)
        .where(Scan.user_id == user_id, Scan.status == "completed")
        .order_by(Scan.created_at.desc())
        .limit(1)
    )
    if scan is None:
        raise DataNotFoundError("No completed scan results are available for this account.")
    return scan


def scan_report(db: Session, user_id: int, scan_id: str, report_type: str) -> dict[str, Any]:
    report = db.scalar(
        select(FinOpsReport).where(
            FinOpsReport.user_id == user_id,
            FinOpsReport.scan_id == scan_id,
            FinOpsReport.report_type == report_type,
        )
    )
    if report is None:
        raise DataNotFoundError(f"{report_type.replace('_', ' ').capitalize()} data is not available for this scan.")
    return report.report_data


def report_rows(db: Session, user_id: int, scan_id: str, report_type: str) -> list[dict[str, Any]]:
    payload = scan_report(db, user_id, scan_id, report_type)
    rows = payload.get("items", [])
    return rows if isinstance(rows, list) else []


def resource_snapshots(db: Session, user_id: int, scan_id: str) -> list[ScanResourceSnapshot]:
    return list(db.scalars(
        select(ScanResourceSnapshot)
        .where(ScanResourceSnapshot.user_id == user_id, ScanResourceSnapshot.scan_id == scan_id)
        .order_by(ScanResourceSnapshot.snapshot_id)
    ).all())
