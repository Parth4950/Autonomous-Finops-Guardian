"""Forecasting dashboard schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ForecastMeta(BaseModel):
    history_days: int
    forecast_days: int
    generated_from: str


class ForecastStats(BaseModel):
    total: int
    waste_high: int
    waste_medium: int
    waste_low: int
    idle: int
    low_usage: int
    healthy: int
    high_usage: int


class WasteDistributionBin(BaseModel):
    category: str
    count: int


class ForecastResource(BaseModel):
    resource_id: str
    resource_type: str
    historical_avg_cpu: float
    forecast_avg_cpu: float
    forecast_min_cpu: float
    forecast_max_cpu: float
    utilization_category: str
    waste_probability: str


class HistoricalPoint(BaseModel):
    date: str
    cpu: float


class ForecastPoint(BaseModel):
    date: str
    cpu: float
    lower: float
    upper: float


class ResourceChartSeries(BaseModel):
    forecast_start: str
    historical: list[HistoricalPoint]
    forecast: list[ForecastPoint]


class ForecastDashboardResponse(BaseModel):
    meta: ForecastMeta
    stats: ForecastStats
    waste_distribution: list[WasteDistributionBin]
    resources: list[ForecastResource]
    chart_data: dict[str, ResourceChartSeries]
