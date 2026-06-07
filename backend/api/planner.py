"""Remediation planning endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_planner_service
from backend.schemas.common import PaginatedResponse
from backend.schemas.planner import RemediationPlanItem
from backend.services.data_loader import DataNotFoundError
from backend.services.planner_service import PlannerService

router = APIRouter(tags=["Planner"])


@router.get(
    "/plans",
    response_model=PaginatedResponse[RemediationPlanItem],
    summary="List remediation plans",
)
def list_remediation_plans(
    service: PlannerService = Depends(get_planner_service),
) -> PaginatedResponse[RemediationPlanItem]:
    """Return planner remediation plans."""
    try:
        items = service.list_plans()
    except DataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PaginatedResponse[RemediationPlanItem](count=len(items), items=items)
