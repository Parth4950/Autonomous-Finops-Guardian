"""Anomaly detection dashboard schemas."""

from __future__ import annotations

from pydantic import BaseModel


class AnomalyStats(BaseModel):
    total: int
    anomalies: int
    normal: int
    contamination_pct: float


class AnomalyHistogramBin(BaseModel):
    bin: str
    count: int


class AnomalyPrediction(BaseModel):
    resource_id: str
    avg_cpu: float
    avg_network_in: float
    avg_network_out: float
    monthly_cost: float
    resource_label: str
    prediction: int
    anomaly_score: float
    prediction_label: str


class AnomalyDashboardResponse(BaseModel):
    stats: AnomalyStats
    histogram: list[AnomalyHistogramBin]
    suspicious: list[AnomalyPrediction]
    scatter: list[AnomalyPrediction]
