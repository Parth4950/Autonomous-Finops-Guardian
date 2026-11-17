"""Authenticated audit result endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import current_user_or_simulation as current_user
from backend.db.session import get_db
from backend.models.auth import User
from backend.schemas.audit import AuditResultItem, ExecutiveReport
from backend.schemas.common import PaginatedResponse
from backend.services.data_loader import DataNotFoundError
from backend.services.owned_scan_data import latest_completed_scan, report_rows, scan_report

router = APIRouter(tags=["Audit"])


@router.get("/audit", response_model=PaginatedResponse[AuditResultItem], summary="List auditor results")
def list_audit_results(db: Session = Depends(get_db), user: User = Depends(current_user)) -> PaginatedResponse[AuditResultItem]:
    try:
        scan = latest_completed_scan(db, user.id)
        rows = report_rows(db, user.id, scan.scan_id, "audit_results")
    except DataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    items = [AuditResultItem.model_validate(row) for row in rows]
    return PaginatedResponse[AuditResultItem](count=len(items), items=items)


@router.get("/audit/report", response_model=ExecutiveReport, summary="Get executive audit report")
def get_executive_report(db: Session = Depends(get_db), user: User = Depends(current_user)) -> ExecutiveReport:
    try:
        scan = latest_completed_scan(db, user.id)
        payload = scan_report(db, user.id, scan.scan_id, "executive_report")
    except DataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ExecutiveReport.model_validate(payload)
