"""Risk assessment endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_risk_service
from backend.schemas.common import PaginatedResponse
from backend.schemas.risk import RiskAssessmentItem
from backend.services.data_loader import DataNotFoundError
from backend.services.risk_service import RiskService

router = APIRouter(tags=["Risk Assessment"])


@router.get(
    "/risk",
    response_model=PaginatedResponse[RiskAssessmentItem],
    summary="List risk assessment results",
)
def list_risk_assessments(
    service: RiskService = Depends(get_risk_service),
) -> PaginatedResponse[RiskAssessmentItem]:
    """Return risk assessment agent outputs."""
    try:
        items = service.list_risk_assessments()
    except DataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PaginatedResponse[RiskAssessmentItem](count=len(items), items=items)
