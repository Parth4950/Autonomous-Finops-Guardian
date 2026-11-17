"""Authenticated risk assessment endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import current_user
from backend.db.session import get_db
from backend.models.auth import User
from backend.schemas.common import PaginatedResponse
from backend.schemas.risk import RiskAssessmentItem
from backend.services.data_loader import DataNotFoundError
from backend.services.owned_scan_data import latest_completed_scan, report_rows

router = APIRouter(tags=["Risk Assessment"])


@router.get("/risk", response_model=PaginatedResponse[RiskAssessmentItem], summary="List risk assessment results")
def list_risk_assessments(db: Session = Depends(get_db), user: User = Depends(current_user)) -> PaginatedResponse[RiskAssessmentItem]:
    try:
        scan = latest_completed_scan(db, user.id)
        rows = report_rows(db, user.id, scan.scan_id, "risk_assessments")
    except DataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    items = [RiskAssessmentItem.model_validate({**row,
        "business_critical": _bool(row.get("business_critical")),
        "attached_to_load_balancer": _bool(row.get("attached_to_load_balancer")),
        "member_of_autoscaling_group": _bool(row.get("member_of_autoscaling_group")),
        "owner_exists": _bool(row.get("owner_exists")),
    }) for row in rows]
    return PaginatedResponse[RiskAssessmentItem](count=len(items), items=items)


def _bool(value: object) -> bool:
    return value is True or str(value).strip().lower() in {"true", "1", "yes"}
