"""Authenticated anomaly dashboard endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import current_user
from backend.db.session import get_db
from backend.models.auth import User
from backend.schemas.anomalies import AnomalyDashboardResponse, AnomalyHistogramBin, AnomalyPrediction, AnomalyStats
from backend.services.data_loader import DataNotFoundError
from backend.services.owned_scan_data import latest_completed_scan, report_rows

router = APIRouter(tags=["Anomaly Detection"])
HISTOGRAM_BINS = [
    ("< -0.04", lambda score: score < -0.04), ("-0.04", lambda score: -0.04 <= score < -0.03),
    ("-0.03", lambda score: -0.03 <= score < -0.02), ("-0.02", lambda score: -0.02 <= score < -0.01),
    ("-0.01", lambda score: -0.01 <= score < 0), ("0", lambda score: 0 <= score < 0.02),
    ("0.02", lambda score: 0.02 <= score < 0.04), ("0.04", lambda score: 0.04 <= score < 0.06),
    ("0.06", lambda score: 0.06 <= score < 0.08), ("0.08", lambda score: score >= 0.08),
]


@router.get("/anomalies", response_model=AnomalyDashboardResponse, summary="Anomaly detection dashboard data")
def get_anomaly_dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)) -> AnomalyDashboardResponse:
    try:
        scan = latest_completed_scan(db, user.id)
        rows = report_rows(db, user.id, scan.scan_id, "anomalies")
    except DataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    predictions = [AnomalyPrediction(
        resource_id=str(row["resource_id"]), avg_cpu=float(row["avg_cpu"]),
        avg_network_in=float(row["avg_network_in"]), avg_network_out=float(row["avg_network_out"]),
        monthly_cost=float(row["monthly_cost"]), resource_label=str(row["resource_label"]),
        prediction=int(row["prediction"]), anomaly_score=float(row["anomaly_score"]),
        prediction_label=str(row["prediction_label"]),
    ) for row in rows]
    anomalous = [item for item in predictions if item.prediction_label == "anomaly"]
    normal = [item for item in predictions if item.prediction_label != "anomaly"]
    histogram = [AnomalyHistogramBin(bin=label, count=sum(predicate(item.anomaly_score) for item in predictions)) for label, predicate in HISTOGRAM_BINS]
    total = len(predictions)
    return AnomalyDashboardResponse(
        stats=AnomalyStats(total=total, anomalies=len(anomalous), normal=len(normal), contamination_pct=round(len(anomalous) / total * 100, 1) if total else 0.0),
        histogram=histogram, suspicious=sorted(anomalous, key=lambda item: item.anomaly_score), scatter=predictions,
    )
