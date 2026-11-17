"""Export Prophet forecast results for the React dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from backend.models.paths import workspace_path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ml.forecasting.prophet_forecaster import (  # noqa: E402
    DEFAULT_FORECAST_RESULTS_PATH,
    DEFAULT_FORECAST_SERIES_CACHE_PATH,
    DEFAULT_HISTORICAL_PATH,
    FORECAST_DAYS,
    HISTORY_DAYS,
    ProphetForecaster,
    build_resource_chart_series,
    load_forecast_series_cache,
)

OUTPUT_PATH = workspace_path(_PROJECT_ROOT / "ml" / "forecasting" / "results" / "forecast_dashboard.json")


def resource_type(resource_id: str, row_type: object = None) -> str:
    if row_type is not None and not pd.isna(row_type):
        normalized = str(row_type).strip()
        if normalized and normalized.lower() not in {"nan", "unknown"}:
            return normalized
    if "-healthy-" in resource_id:
        return "healthy"
    if "-zombie-" in resource_id:
        return "zombie"
    if "-seasonal-" in resource_id:
        return "seasonal"
    return "heuristic_fallback"


def load_chart_data(
    historical: pd.DataFrame,
    resource_ids: list[str],
    cache_path: Path | None = None,
) -> dict[str, dict]:
    """Load cached chart series or rebuild as a fallback for legacy pipeline runs."""
    chart_data: dict[str, dict] = {}
    resolved_cache = cache_path or workspace_path(
        _PROJECT_ROOT / "ml" / "forecasting" / "results" / "forecast_series_cache.json"
    )

    try:
        chart_data = load_forecast_series_cache(resolved_cache)
        missing = [resource_id for resource_id in resource_ids if resource_id not in chart_data]
        if not missing:
            print(f"Loaded forecast chart cache for {len(chart_data)} resources.")
            return chart_data
        print(f"Forecast cache missing {len(missing)} resource(s); rebuilding only those entries.")
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        print("Forecast series cache unavailable; rebuilding chart data with Prophet.")
        missing = resource_ids

    forecaster = ProphetForecaster()
    for resource_id in missing:
        if not historical.empty and "resource_id" in historical.columns:
            resource_frame = historical[historical["resource_id"] == resource_id]
        else:
            resource_frame = pd.DataFrame(columns=["resource_id", "date", "cpu_utilization", "resource_type"])
        forecaster.forecast_resource(resource_id, resource_frame)
        chart_data[resource_id] = build_resource_chart_series(
            historical,
            forecaster.get_forecast_detail(resource_id),
            resource_id,
        )

    return chart_data


def main() -> int:
    historical_path = workspace_path(_PROJECT_ROOT / "ml" / "forecasting" / "data" / "historical_cpu_usage.csv")
    results_path = workspace_path(_PROJECT_ROOT / "ml" / "forecasting" / "results" / "forecast_results.csv")
    cache_path = workspace_path(_PROJECT_ROOT / "ml" / "forecasting" / "results" / "forecast_series_cache.json")
    output_path = workspace_path(_PROJECT_ROOT / "ml" / "forecasting" / "results" / "forecast_dashboard.json")

    if not results_path.exists():
        print("Run prophet_forecaster.py first to generate CSV outputs.")
        return 1

    if historical_path.exists():
        try:
            historical = pd.read_csv(historical_path, parse_dates=["date"])
        except pd.errors.EmptyDataError:
            historical = pd.DataFrame(columns=["resource_id", "date", "cpu_utilization", "resource_type"])
    else:
        historical = pd.DataFrame(columns=["resource_id", "date", "cpu_utilization", "resource_type"])

    results = pd.read_csv(results_path)
    resource_ids = results["resource_id"].tolist()

    utilization_counts = results["utilization_category"].value_counts().to_dict()
    waste_counts = results["waste_probability"].value_counts().reindex(
        ["high", "medium", "low"], fill_value=0
    )

    resources = []
    for _, row in results.iterrows():
        rid = str(row["resource_id"])
        resources.append(
            {
                "resource_id": rid,
                "resource_type": resource_type(rid, row.get("resource_type")),
                "historical_avg_cpu": round(float(row["historical_avg_cpu"]), 2),
                "forecast_avg_cpu": round(float(row["forecast_avg_cpu"]), 2),
                "forecast_min_cpu": round(float(row["forecast_min_cpu"]), 2),
                "forecast_max_cpu": round(float(row["forecast_max_cpu"]), 2),
                "utilization_category": row["utilization_category"],
                "waste_probability": row["waste_probability"],
            }
        )

    chart_data = load_chart_data(historical, resource_ids, cache_path=cache_path)
    history_days = 0 if historical.empty else HISTORY_DAYS

    payload = {
        "meta": {
            "history_days": history_days,
            "forecast_days": FORECAST_DAYS,
            "generated_from": str(results_path.relative_to(workspace_path(_PROJECT_ROOT))),
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Exported forecast data to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
