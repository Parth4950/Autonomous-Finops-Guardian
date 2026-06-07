"""Forecasting dashboard service."""

from __future__ import annotations

import json
from pathlib import Path

from backend.models.paths import FORECAST_DASHBOARD_JSON, FORECAST_DASHBOARD_FALLBACK
from backend.schemas.forecast import ForecastDashboardResponse
from backend.services.data_loader import DataNotFoundError


class ForecastService:
    """Serve Prophet forecast dashboard payloads."""

    def get_dashboard(self) -> ForecastDashboardResponse:
        """Return forecasting dashboard data from exported JSON."""
        payload = self._load_dashboard_json()
        return ForecastDashboardResponse.model_validate(payload)

    @staticmethod
    def _load_dashboard_json() -> dict:
        for path in (FORECAST_DASHBOARD_JSON, FORECAST_DASHBOARD_FALLBACK):
            if path.exists():
                with open(path, encoding="utf-8") as handle:
                    return json.load(handle)

        raise DataNotFoundError(
            "Forecast dashboard data not found. Run ml/forecasting/export_forecast_json.py first."
        )
