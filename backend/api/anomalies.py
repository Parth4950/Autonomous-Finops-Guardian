"""Anomaly detection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_anomaly_service
from backend.schemas.anomalies import AnomalyDashboardResponse
from backend.services.anomaly_service import AnomalyService
from backend.services.data_loader import DataNotFoundError

router = APIRouter(tags=["Anomaly Detection"])


@router.get(
    "/anomalies",
    response_model=AnomalyDashboardResponse,
    summary="Anomaly detection dashboard data",
)
def get_anomaly_dashboard(
    service: AnomalyService = Depends(get_anomaly_service),
) -> AnomalyDashboardResponse:
    """Return Isolation Forest anomaly detection results for the dashboard."""
    try:
        return service.get_dashboard()
    except DataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
