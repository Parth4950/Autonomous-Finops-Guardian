"""Waste scoring schemas."""

from __future__ import annotations

from pydantic import BaseModel


class WasteScoreItem(BaseModel):
    """Combined waste scoring result for a resource."""

    resource_id: str
    waste_score: float | None = None
    waste_probability: str | None = None
    utilization_category: str | None = None
    forecast_avg_cpu: float | None = None
    anomaly_score: float | None = None
    prediction_label: str | None = None
    monthly_cost: float | None = None
