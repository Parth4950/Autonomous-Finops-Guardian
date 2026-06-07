"""Anomaly detection dashboard service."""

from __future__ import annotations

import pandas as pd

from backend.models.paths import WASTE_PREDICTIONS_CSV
from backend.schemas.anomalies import (
    AnomalyDashboardResponse,
    AnomalyHistogramBin,
    AnomalyPrediction,
    AnomalyStats,
)
from backend.services.data_loader import DataLoader, DataNotFoundError

HISTOGRAM_BINS = [
    ("< -0.04", lambda score: score < -0.04),
    ("-0.04", lambda score: -0.04 <= score < -0.03),
    ("-0.03", lambda score: -0.03 <= score < -0.02),
    ("-0.02", lambda score: -0.02 <= score < -0.01),
    ("-0.01", lambda score: -0.01 <= score < 0),
    ("0", lambda score: 0 <= score < 0.02),
    ("0.02", lambda score: 0.02 <= score < 0.04),
    ("0.04", lambda score: 0.04 <= score < 0.06),
    ("0.06", lambda score: 0.06 <= score < 0.08),
    ("0.08", lambda score: score >= 0.08),
]


class AnomalyService:
    """Build anomaly dashboard payloads from Isolation Forest outputs."""

    def __init__(self, loader: DataLoader | None = None) -> None:
        self._loader = loader or DataLoader()

    def get_dashboard(self) -> AnomalyDashboardResponse:
        """Return anomaly detection dashboard data."""
        try:
            records = self._loader.read_csv(WASTE_PREDICTIONS_CSV)
        except DataNotFoundError as exc:
            raise DataNotFoundError(
                "Anomaly predictions not found. Run ml/isolation_forest/isolation_detector.py first."
            ) from exc

        dataframe = pd.DataFrame(records)
        predictions = [self._to_prediction(row) for _, row in dataframe.iterrows()]
        anomalies = [item for item in predictions if item.prediction_label == "anomaly"]
        normal = [item for item in predictions if item.prediction_label != "anomaly"]
        total = len(predictions)

        stats = AnomalyStats(
            total=total,
            anomalies=len(anomalies),
            normal=len(normal),
            contamination_pct=round((len(anomalies) / total) * 100, 1) if total else 0.0,
        )

        suspicious = sorted(anomalies, key=lambda item: item.anomaly_score)
        histogram = self._build_histogram(dataframe)

        return AnomalyDashboardResponse(
            stats=stats,
            histogram=histogram,
            suspicious=suspicious,
            scatter=predictions,
        )

    @staticmethod
    def _to_prediction(row: pd.Series) -> AnomalyPrediction:
        return AnomalyPrediction(
            resource_id=str(row["resource_id"]),
            avg_cpu=float(row["avg_cpu"]),
            avg_network_in=float(row["avg_network_in"]),
            avg_network_out=float(row["avg_network_out"]),
            monthly_cost=float(row["monthly_cost"]),
            resource_label=str(row["resource_label"]),
            prediction=int(row["prediction"]),
            anomaly_score=float(row["anomaly_score"]),
            prediction_label=str(row["prediction_label"]),
        )

    @staticmethod
    def _build_histogram(dataframe: pd.DataFrame) -> list[AnomalyHistogramBin]:
        scores = dataframe["anomaly_score"].astype(float)
        return [
            AnomalyHistogramBin(
                bin=label,
                count=int(scores.map(predicate).sum()),
            )
            for label, predicate in HISTOGRAM_BINS
        ]
