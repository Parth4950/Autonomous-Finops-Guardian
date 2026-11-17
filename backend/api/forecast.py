"""Authenticated forecast dashboard endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import current_user
from backend.db.session import get_db
from backend.models.auth import User
from backend.schemas.forecast import ForecastDashboardResponse
from backend.services.data_loader import DataNotFoundError
from backend.services.owned_scan_data import latest_completed_scan, scan_report

router = APIRouter(tags=["Forecasting"])


@router.get("/forecast", response_model=ForecastDashboardResponse, summary="Forecasting dashboard data")
def get_forecast_dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)) -> ForecastDashboardResponse:
    try:
        scan = latest_completed_scan(db, user.id)
        payload = scan_report(db, user.id, scan.scan_id, "forecast_dashboard")
    except DataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ForecastDashboardResponse.model_validate(payload)
