"""Forecasting endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_forecast_service
from backend.schemas.forecast import ForecastDashboardResponse
from backend.services.data_loader import DataNotFoundError
from backend.services.forecast_service import ForecastService

router = APIRouter(tags=["Forecasting"])


@router.get(
    "/forecast",
    response_model=ForecastDashboardResponse,
    summary="Forecasting dashboard data",
)
def get_forecast_dashboard(
    service: ForecastService = Depends(get_forecast_service),
) -> ForecastDashboardResponse:
    """Return Prophet forecast results for the dashboard."""
    try:
        return service.get_dashboard()
    except DataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
