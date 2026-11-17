"""Authenticated remediation plan endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import current_user_or_simulation as current_user
from backend.db.session import get_db
from backend.models.auth import User
from backend.schemas.common import PaginatedResponse
from backend.schemas.planner import RemediationPlanItem
from backend.services.data_loader import DataNotFoundError
from backend.services.owned_scan_data import latest_completed_scan, report_rows

router = APIRouter(tags=["Planner"])


@router.get("/plans", response_model=PaginatedResponse[RemediationPlanItem], summary="List remediation plans")
def list_remediation_plans(db: Session = Depends(get_db), user: User = Depends(current_user)) -> PaginatedResponse[RemediationPlanItem]:
    try:
        scan = latest_completed_scan(db, user.id)
        rows = report_rows(db, user.id, scan.scan_id, "plans")
    except DataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PaginatedResponse[RemediationPlanItem](count=len(rows), items=[RemediationPlanItem.model_validate(row) for row in rows])
