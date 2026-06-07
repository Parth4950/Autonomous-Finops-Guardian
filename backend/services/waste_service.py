"""Waste scoring service."""

from __future__ import annotations

from backend.models.paths import RISK_ASSESSMENT_CSV, WASTE_FORECAST_CSV, WASTE_PREDICTIONS_CSV
from backend.schemas.waste import WasteScoreItem
from backend.services.data_loader import DataLoader, DataNotFoundError


class WasteService:
    """Combine waste scores from risk, forecasting, and anomaly detection outputs."""

    def __init__(self, loader: DataLoader | None = None) -> None:
        self._loader = loader or DataLoader()

    def list_waste_scores(self) -> list[WasteScoreItem]:
        """Return merged waste scoring results across ML and risk pipelines."""
        risk_records = {
            row["resource_id"]: row
            for row in self._loader.read_csv(RISK_ASSESSMENT_CSV)
        }

        forecast_records: dict[str, dict] = {}
        try:
            forecast_records = {
                row["resource_id"]: row
                for row in self._loader.read_csv(WASTE_FORECAST_CSV)
            }
        except DataNotFoundError:
            pass

        prediction_records: dict[str, dict] = {}
        try:
            prediction_records = {
                row["resource_id"]: row
                for row in self._loader.read_csv(WASTE_PREDICTIONS_CSV)
            }
        except DataNotFoundError:
            pass

        resource_ids = set(risk_records) | set(forecast_records) | set(prediction_records)
        results: list[WasteScoreItem] = []

        for resource_id in sorted(resource_ids):
            risk = risk_records.get(resource_id, {})
            forecast = forecast_records.get(resource_id, {})
            prediction = prediction_records.get(resource_id, {})

            results.append(
                WasteScoreItem(
                    resource_id=resource_id,
                    waste_score=_optional_float(risk.get("waste_score")),
                    waste_probability=_optional_str(
                        risk.get("waste_probability") or forecast.get("waste_probability")
                    ),
                    utilization_category=_optional_str(forecast.get("utilization_category")),
                    forecast_avg_cpu=_optional_float(forecast.get("forecast_avg_cpu")),
                    anomaly_score=_optional_float(prediction.get("anomaly_score")),
                    prediction_label=_optional_str(prediction.get("prediction_label")),
                    monthly_cost=_optional_float(risk.get("monthly_cost")),
                )
            )

        return results


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)  # type: ignore[arg-type]


def _optional_str(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)
