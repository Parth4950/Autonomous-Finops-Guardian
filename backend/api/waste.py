"""Waste scoring endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_waste_service
from backend.schemas.common import PaginatedResponse
from backend.schemas.waste import WasteScoreItem
from backend.services.data_loader import DataNotFoundError
from backend.services.waste_service import WasteService

router = APIRouter(tags=["Waste Scoring"])


@router.get(
    "/waste",
    response_model=PaginatedResponse[WasteScoreItem],
    summary="List waste scoring results",
)
def list_waste_scores(
    service: WasteService = Depends(get_waste_service),
) -> PaginatedResponse[WasteScoreItem]:
    """Return merged waste scores from risk, forecasting, and anomaly detection."""
    try:
        items = service.list_waste_scores()
    except DataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PaginatedResponse[WasteScoreItem](count=len(items), items=items)
