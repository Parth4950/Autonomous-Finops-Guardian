"""Authenticated merged waste scoring endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import current_user
from backend.db.session import get_db
from backend.models.auth import User
from backend.schemas.common import PaginatedResponse
from backend.schemas.waste import WasteScoreItem
from backend.services.data_loader import DataNotFoundError
from backend.services.owned_scan_data import latest_completed_scan, report_rows

router = APIRouter(tags=["Waste Scoring"])


@router.get("/waste", response_model=PaginatedResponse[WasteScoreItem], summary="List waste scoring results")
def list_waste_scores(db: Session = Depends(get_db), user: User = Depends(current_user)) -> PaginatedResponse[WasteScoreItem]:
    try:
        scan = latest_completed_scan(db, user.id)
        risk = {str(row["resource_id"]): row for row in report_rows(db, user.id, scan.scan_id, "risk_assessments")}
        forecasts = {str(row["resource_id"]): row for row in report_rows(db, user.id, scan.scan_id, "forecast_results")}
        anomalies = {str(row["resource_id"]): row for row in report_rows(db, user.id, scan.scan_id, "anomalies")}
    except DataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    ids = set(risk) | set(forecasts) | set(anomalies)
    items = [WasteScoreItem(
        resource_id=resource_id,
        waste_score=_float(risk.get(resource_id, {}).get("waste_score")),
        waste_probability=_string(risk.get(resource_id, {}).get("waste_probability") or forecasts.get(resource_id, {}).get("waste_probability")),
        utilization_category=_string(forecasts.get(resource_id, {}).get("utilization_category")),
        forecast_avg_cpu=_float(forecasts.get(resource_id, {}).get("forecast_avg_cpu")),
        anomaly_score=_float(anomalies.get(resource_id, {}).get("anomaly_score")),
        prediction_label=_string(anomalies.get(resource_id, {}).get("prediction_label")),
        monthly_cost=_float(risk.get(resource_id, {}).get("monthly_cost")),
    ) for resource_id in sorted(ids)]
    return PaginatedResponse[WasteScoreItem](count=len(items), items=items)


def _float(value: object) -> float | None:
    return None if value in (None, "") else float(value)


def _string(value: object) -> str | None:
    return None if value in (None, "") else str(value)
