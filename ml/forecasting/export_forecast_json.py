"""Export Prophet forecast results for the React dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ml.forecasting.prophet_forecaster import (  # noqa: E402
    DEFAULT_FORECAST_RESULTS_PATH,
    DEFAULT_HISTORICAL_PATH,
    FORECAST_DAYS,
    HISTORY_DAYS,
    ProphetForecaster,
)

OUTPUT_PATH = _PROJECT_ROOT / "frontend" / "src" / "data" / "forecast-predictions.json"


def resource_type(resource_id: str) -> str:
    if "-healthy-" in resource_id:
        return "healthy"
    if "-zombie-" in resource_id:
        return "zombie"
    if "-seasonal-" in resource_id:
        return "seasonal"
    return "unknown"


def build_series(
    historical: pd.DataFrame,
    forecaster: ProphetForecaster,
    resource_id: str,
) -> dict:
    history = historical[historical["resource_id"] == resource_id].sort_values("date")
    forecast = forecaster.get_forecast_detail(resource_id).copy()
    forecast["ds"] = pd.to_datetime(forecast["ds"])
    forecast_tail = forecast.tail(FORECAST_DAYS)
    last_history_date = pd.to_datetime(history["date"].max())

    return {
        "forecast_start": last_history_date.date().isoformat(),
        "historical": [
            {
                "date": pd.to_datetime(row["date"]).date().isoformat(),
                "cpu": round(float(row["cpu_utilization"]), 2),
            }
            for _, row in history.iterrows()
        ],
        "forecast": [
            {
                "date": row["ds"].date().isoformat(),
                "cpu": round(float(row["yhat"]), 2),
                "lower": round(float(max(0, row["yhat_lower"])), 2),
                "upper": round(float(min(100, row["yhat_upper"])), 2),
            }
            for _, row in forecast_tail.iterrows()
        ],
    }


def main() -> int:
    historical_path = DEFAULT_HISTORICAL_PATH
    results_path = DEFAULT_FORECAST_RESULTS_PATH

    if not historical_path.exists() or not results_path.exists():
        print("Run prophet_forecaster.py first to generate CSV outputs.")
        return 1

    historical = pd.read_csv(historical_path, parse_dates=["date"])
    results = pd.read_csv(results_path)

    forecaster = ProphetForecaster()
    forecaster.forecast_all(historical)

    utilization_counts = (
        results["utilization_category"].value_counts().to_dict()
    )
    waste_counts = results["waste_probability"].value_counts().reindex(
        ["high", "medium", "low"], fill_value=0
    )

    resources = []
    for _, row in results.iterrows():
        rid = row["resource_id"]
        resources.append(
            {
                "resource_id": rid,
                "resource_type": resource_type(rid),
                "historical_avg_cpu": round(float(row["historical_avg_cpu"]), 2),
                "forecast_avg_cpu": round(float(row["forecast_avg_cpu"]), 2),
                "forecast_min_cpu": round(float(row["forecast_min_cpu"]), 2),
                "forecast_max_cpu": round(float(row["forecast_max_cpu"]), 2),
                "utilization_category": row["utilization_category"],
                "waste_probability": row["waste_probability"],
            }
        )

    chart_data = {
        rid: build_series(historical, forecaster, rid)
        for rid in results["resource_id"].tolist()
    }

    payload = {
        "meta": {
            "history_days": HISTORY_DAYS,
            "forecast_days": FORECAST_DAYS,
            "generated_from": str(results_path.relative_to(_PROJECT_ROOT)),
        },
        "stats": {
            "total": len(results),
            "waste_high": int(waste_counts["high"]),
            "waste_medium": int(waste_counts["medium"]),
            "waste_low": int(waste_counts["low"]),
            "idle": int(utilization_counts.get("idle", 0)),
            "low_usage": int(utilization_counts.get("low_usage", 0)),
            "healthy": int(utilization_counts.get("healthy", 0)),
            "high_usage": int(utilization_counts.get("high_usage", 0)),
        },
        "waste_distribution": [
            {"category": "high", "count": int(waste_counts["high"])},
            {"category": "medium", "count": int(waste_counts["medium"])},
            {"category": "low", "count": int(waste_counts["low"])},
        ],
        "resources": resources,
        "chart_data": chart_data,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Exported forecast data to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
