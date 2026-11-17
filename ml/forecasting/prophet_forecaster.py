"""
Prophet-based CPU utilization forecasting for cloud FinOps waste detection.

Generates synthetic historical utilization, trains per-resource Prophet models,
classifies forecast trends, and estimates waste probability.
"""

from __future__ import annotations

import json
import logging
import sys
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from prophet import Prophet

# Allow `python ml/forecasting/prophet_forecaster.py` from any working directory.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

warnings.filterwarnings("ignore", category=FutureWarning)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

from backend.models.paths import workspace_path

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = workspace_path(MODULE_DIR / "data")
DEFAULT_RESULTS_DIR = workspace_path(MODULE_DIR / "results")
DEFAULT_FIGURES_DIR = workspace_path(MODULE_DIR / "figures")
DEFAULT_HISTORICAL_PATH = DEFAULT_DATA_DIR / "historical_cpu_usage.csv"
DEFAULT_FORECAST_RESULTS_PATH = DEFAULT_RESULTS_DIR / "forecast_results.csv"
DEFAULT_FORECAST_SERIES_CACHE_PATH = DEFAULT_RESULTS_DIR / "forecast_series_cache.json"

RANDOM_SEED = 42
HISTORY_DAYS = 90
FORECAST_DAYS = 30
TOTAL_RESOURCES = 100
TOP_N_WASTE = 20
MIN_PROPHET_POINTS = 7

RESOURCE_COUNTS: dict[str, int] = {
    "healthy": 60,
    "zombie": 20,
    "seasonal": 20,
}

UtilizationCategory = Literal["idle", "low_usage", "healthy", "high_usage"]
WasteProbability = Literal["high", "medium", "low"]

WASTE_PRIORITY: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class ForecastSummary:
    """Aggregate counts across utilization and waste categories."""

    total_resources: int
    idle: int
    low_usage: int
    healthy: int
    high_usage: int
    waste_high: int
    waste_medium: int
    waste_low: int


class HistoricalDataError(ValueError):
    """Raised when historical utilization data is invalid or missing."""


class HistoricalCPUDataGenerator:
    """Generate realistic synthetic daily CPU utilization histories."""

    def __init__(self, seed: int = RANDOM_SEED) -> None:
        self._rng = np.random.default_rng(seed)
        self._start_date = datetime.now(UTC).date() - timedelta(days=HISTORY_DAYS)

    def generate(self) -> pd.DataFrame:
        """
        Generate 90-day CPU histories for 100 resources across three categories.

        Returns:
            DataFrame with resource_id, date, cpu_utilization, resource_type.
        """
        records: list[dict[str, Any]] = []

        for resource_type, count in RESOURCE_COUNTS.items():
            for index in range(1, count + 1):
                resource_id = f"res-{resource_type}-{index:03d}"
                series = self._generate_resource_series(resource_type)
                dates = [
                    self._start_date + timedelta(days=day) for day in range(HISTORY_DAYS)
                ]

                for date_value, cpu_value in zip(dates, series, strict=True):
                    records.append(
                        {
                            "resource_id": resource_id,
                            "date": date_value.isoformat(),
                            "cpu_utilization": round(float(cpu_value), 2),
                            "resource_type": resource_type,
                        }
                    )

        dataframe = pd.DataFrame(records)
        logger.info(
            "Generated %d days x %d resources (%d rows)",
            HISTORY_DAYS,
            TOTAL_RESOURCES,
            len(dataframe),
        )
        return dataframe

    def _generate_resource_series(self, resource_type: str) -> np.ndarray:
        """Generate a 90-day CPU utilization array for a resource category."""
        if resource_type == "healthy":
            base = self._rng.uniform(50, 65)
            noise = self._rng.normal(0, 6, HISTORY_DAYS)
            values = base + noise
            return np.clip(values, 40, 80)

        if resource_type == "zombie":
            base = self._rng.uniform(1.5, 3.0)
            noise = self._rng.normal(0, 0.6, HISTORY_DAYS)
            values = base + noise
            return np.clip(values, 0, 5)

        if resource_type == "seasonal":
            day_indices = np.arange(HISTORY_DAYS)
            weekly_cycle = 18 * np.sin(2 * np.pi * day_indices / 7)
            biweekly_spike = 12 * np.sin(2 * np.pi * day_indices / 14)
            base = 35 + weekly_cycle + biweekly_spike
            noise = self._rng.normal(0, 4, HISTORY_DAYS)
            monday_boost = np.zeros(HISTORY_DAYS)
            for day in day_indices:
                weekday = (self._start_date + timedelta(days=int(day))).weekday()
                if weekday == 0:
                    monday_boost[day] = self._rng.uniform(10, 20)
            values = base + noise + monday_boost
            return np.clip(values, 5, 85)

        raise ValueError(f"Unknown resource type: {resource_type}")

    def save(self, dataframe: pd.DataFrame, output_path: Path = DEFAULT_HISTORICAL_PATH) -> Path:
        """Persist generated historical data to CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(output_path, index=False)
        logger.info("Historical CPU data saved to %s", output_path)
        return output_path


class ProphetForecaster:
    """
    Train Prophet models per resource and forecast future CPU utilization.

    Designed for integration with the Predictor Agent alongside Isolation Forest.
    """

    def __init__(self, forecast_days: int = FORECAST_DAYS) -> None:
        self._forecast_days = forecast_days
        self._historical_data: pd.DataFrame | None = None
        self._forecast_details: dict[str, pd.DataFrame] = {}

    @staticmethod
    def classify_utilization(forecast_avg_cpu: float) -> UtilizationCategory:
        """
        Map average forecast CPU to a utilization trend category.

        Args:
            forecast_avg_cpu: Mean forecasted CPU over the forecast horizon.

        Returns:
            One of idle, low_usage, healthy, or high_usage.
        """
        if forecast_avg_cpu < 5:
            return "idle"
        if forecast_avg_cpu < 20:
            return "low_usage"
        if forecast_avg_cpu <= 70:
            return "healthy"
        return "high_usage"

    @staticmethod
    def classify_waste_probability(
        historical_avg_cpu: float,
        forecast_avg_cpu: float,
    ) -> WasteProbability:
        """
        Estimate waste probability from historical and forecast utilization.

        Rules:
            - Persistently idle history and forecast → high
            - Low history but rising forecast → medium
            - Healthy utilization → low
        """
        if historical_avg_cpu < 5 and forecast_avg_cpu < 5:
            return "high"

        if historical_avg_cpu < 20 and forecast_avg_cpu > historical_avg_cpu * 1.1:
            return "medium"

        if historical_avg_cpu >= 20 and forecast_avg_cpu >= 20:
            return "low"

        if historical_avg_cpu < 20 and forecast_avg_cpu < 20:
            return "high"

        return "medium"

    def load_historical_data(
        self,
        data_path: Path = DEFAULT_HISTORICAL_PATH,
    ) -> pd.DataFrame:
        """
        Load historical CPU utilization CSV.

        Raises:
            HistoricalDataError: If file is missing or malformed.
        """
        if not data_path.exists():
            raise HistoricalDataError(
                f"Historical data not found at {data_path}. "
                "Run the pipeline to generate synthetic history first."
            )

        dataframe = pd.read_csv(data_path, parse_dates=["date"])
        required = {"resource_id", "date", "cpu_utilization", "resource_type"}
        if not required.issubset(dataframe.columns):
            raise HistoricalDataError(
                f"Historical data missing columns: {required - set(dataframe.columns)}"
            )

        self._historical_data = dataframe
        logger.info("Loaded historical data — %d rows", len(dataframe))
        return dataframe

    def _prepare_prophet_frame(self, resource_frame: pd.DataFrame) -> pd.DataFrame:
        """Convert resource history to Prophet-compatible ds/y format."""
        prophet_frame = resource_frame[["date", "cpu_utilization"]].copy()
        prophet_frame.columns = ["ds", "y"]
        return prophet_frame.sort_values("ds")

    def _resource_type(self, resource_frame: pd.DataFrame) -> str:
        if "resource_type" in resource_frame.columns and not resource_frame.empty:
            return str(resource_frame["resource_type"].iloc[0])
        return "aws"

    def _heuristic_forecast(
        self,
        resource_id: str,
        resource_frame: pd.DataFrame,
        prophet_frame: pd.DataFrame,
        baseline_cpu: float | None = None,
    ) -> dict[str, Any]:
        """Flat-line deterministic fallback forecast when CloudWatch history is unavailable or too short."""
        if len(prophet_frame):
            historical_avg_cpu = round(float(prophet_frame["y"].mean()), 2)
        elif baseline_cpu is not None:
            historical_avg_cpu = round(float(baseline_cpu), 2)
        else:
            historical_avg_cpu = 0.0
        forecast_avg_cpu = historical_avg_cpu
        forecast_min_cpu = historical_avg_cpu
        forecast_max_cpu = historical_avg_cpu

        if prophet_frame.empty:
            last_date = pd.Timestamp.utcnow().normalize()
            history_part = pd.DataFrame(columns=["ds", "yhat", "yhat_lower", "yhat_upper"])
        else:
            last_date = pd.to_datetime(prophet_frame["ds"].max())
            history_part = prophet_frame.rename(columns={"y": "yhat"}).copy()
            history_part["yhat_lower"] = history_part["yhat"]
            history_part["yhat_upper"] = history_part["yhat"]

        future_dates = pd.date_range(
            last_date + pd.Timedelta(days=1),
            periods=self._forecast_days,
            freq="D",
        )
        future = pd.DataFrame(
            {
                "ds": future_dates,
                "yhat": forecast_avg_cpu,
                "yhat_lower": max(0.0, forecast_avg_cpu - 5.0),
                "yhat_upper": min(100.0, forecast_avg_cpu + 5.0),
            }
        )
        self._forecast_details[resource_id] = (
            future.copy()
            if history_part.empty
            else pd.concat([history_part, future], ignore_index=True)
        )

        utilization_category = self.classify_utilization(forecast_avg_cpu)
        waste_probability = self.classify_waste_probability(
            historical_avg_cpu=historical_avg_cpu,
            forecast_avg_cpu=forecast_avg_cpu,
        )

        return {
            "resource_id": resource_id,
            "resource_type": "heuristic_fallback",
            "historical_avg_cpu": historical_avg_cpu,
            "forecast_avg_cpu": forecast_avg_cpu,
            "forecast_min_cpu": forecast_min_cpu,
            "forecast_max_cpu": forecast_max_cpu,
            "utilization_category": utilization_category,
            "waste_probability": waste_probability,
        }

    def forecast_resource(self, resource_id: str, resource_frame: pd.DataFrame) -> dict[str, Any]:
        """
        Train Prophet and forecast CPU for a single resource.

        Args:
            resource_id: Resource identifier.
            resource_frame: Historical rows for the resource.

        Returns:
            Dictionary with forecast metrics and classifications.
        """
        prophet_frame = self._prepare_prophet_frame(resource_frame)

        if prophet_frame.empty or len(prophet_frame) < MIN_PROPHET_POINTS:
            logger.info(
                "Using heuristic forecast for %s (%d day(s) of CPU history)",
                resource_id,
                len(prophet_frame),
            )
            return self._heuristic_forecast(resource_id, resource_frame, prophet_frame)

        historical_avg_cpu = round(float(prophet_frame["y"].mean()), 2)

        try:
            model = Prophet(
                daily_seasonality=False,
                weekly_seasonality=len(prophet_frame) >= 14,
                yearly_seasonality=False,
                changepoint_prior_scale=0.05,
            )
            model.fit(prophet_frame)

            future = model.make_future_dataframe(periods=self._forecast_days, freq="D")
            forecast = model.predict(future)
            forecast["yhat"] = forecast["yhat"].clip(0, 100)

            forecast_tail = forecast.tail(self._forecast_days)
            forecast_avg_cpu = round(float(forecast_tail["yhat"].mean()), 2)
            forecast_min_cpu = round(float(forecast_tail["yhat"].min()), 2)
            forecast_max_cpu = round(float(forecast_tail["yhat"].max()), 2)

            self._forecast_details[resource_id] = forecast.copy()
        except Exception as exc:
            logger.warning("Prophet failed for %s, using heuristic forecast: %s", resource_id, exc)
            return self._heuristic_forecast(resource_id, resource_frame, prophet_frame)

        utilization_category = self.classify_utilization(forecast_avg_cpu)
        waste_probability = self.classify_waste_probability(
            historical_avg_cpu=historical_avg_cpu,
            forecast_avg_cpu=forecast_avg_cpu,
        )

        return {
            "resource_id": resource_id,
            "resource_type": self._resource_type(resource_frame),
            "historical_avg_cpu": historical_avg_cpu,
            "forecast_avg_cpu": forecast_avg_cpu,
            "forecast_min_cpu": forecast_min_cpu,
            "forecast_max_cpu": forecast_max_cpu,
            "utilization_category": utilization_category,
            "waste_probability": waste_probability,
        }

    def forecast_all(self, historical_data: pd.DataFrame | None = None) -> pd.DataFrame:
        """
        Forecast CPU utilization for every resource in the historical dataset.

        Returns:
            DataFrame with per-resource forecast summaries.
        """
        if historical_data is None:
            if self._historical_data is None:
                self.load_historical_data()
            historical_data = self._historical_data

        if historical_data is None or historical_data.empty:
            raise HistoricalDataError("No historical data available for forecasting.")

        results: list[dict[str, Any]] = []
        resource_ids = historical_data["resource_id"].unique()

        logger.info("Forecasting %d resources (%d-day horizon)...", len(resource_ids), self._forecast_days)

        for index, resource_id in enumerate(resource_ids, start=1):
            resource_frame = historical_data[historical_data["resource_id"] == resource_id]
            try:
                result = self.forecast_resource(resource_id, resource_frame)
                results.append(result)
            except Exception as exc:
                logger.error("Forecast failed for %s: %s", resource_id, exc)

            if index % 20 == 0:
                logger.info("Forecast progress: %d / %d", index, len(resource_ids))

        results_frame = pd.DataFrame(results)
        if results_frame.empty:
            raise HistoricalDataError(
                f"Forecasting failed for all {len(resource_ids)} resource(s). "
                "Verify CloudWatch CPU metrics are available for discovered EC2 instances."
            )
        logger.info("Forecasting complete for %d resources", len(results_frame))
        return results_frame

    def get_forecast_detail(self, resource_id: str) -> pd.DataFrame:
        """Return full Prophet forecast DataFrame for a resource."""
        if resource_id not in self._forecast_details:
            raise KeyError(f"No forecast detail stored for resource: {resource_id}")
        return self._forecast_details[resource_id]

    def save_series_cache(
        self,
        historical_data: pd.DataFrame,
        output_path: Path | None = None,
    ) -> Path:
        """Persist per-resource chart series so export does not retrain Prophet models."""
        resolved_path = output_path or workspace_path(MODULE_DIR / "results" / "forecast_series_cache.json")
        chart_data = {
            resource_id: build_resource_chart_series(
                historical_data,
                self._forecast_details[resource_id],
                resource_id,
            )
            for resource_id in self._forecast_details
        }
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text(json.dumps(chart_data), encoding="utf-8")
        logger.info("Saved forecast series cache for %d resources to %s", len(chart_data), resolved_path)
        return resolved_path


def build_resource_chart_series(
    historical: pd.DataFrame,
    forecast_detail: pd.DataFrame,
    resource_id: str,
    forecast_days: int = FORECAST_DAYS,
) -> dict[str, Any]:
    """Build dashboard chart payload for one resource from stored Prophet output."""
    if historical is not None and not historical.empty and "resource_id" in historical.columns:
        history = historical[historical["resource_id"] == resource_id].sort_values("date")
    else:
        history = pd.DataFrame(columns=["resource_id", "date", "cpu_utilization"])
    forecast = forecast_detail.copy()
    forecast["ds"] = pd.to_datetime(forecast["ds"])
    forecast_tail = forecast.tail(forecast_days)
    if not history.empty:
        last_history_date = pd.to_datetime(history["date"].max())
    elif not forecast_tail.empty:
        last_history_date = pd.to_datetime(forecast_tail["ds"].min()) - pd.Timedelta(days=1)
    else:
        last_history_date = pd.Timestamp.utcnow().normalize()

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


def load_forecast_series_cache(
    cache_path: Path = DEFAULT_FORECAST_SERIES_CACHE_PATH,
) -> dict[str, Any]:
    """Load cached chart series written during the Prophet pipeline step."""
    if not cache_path.exists():
        raise FileNotFoundError(f"Forecast series cache not found at {cache_path}")
    with open(cache_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Forecast series cache must be a JSON object.")
    return payload


class ForecastAnalyzer:
    """Compute aggregate forecast summaries."""

    @staticmethod
    def summarize(results: pd.DataFrame) -> ForecastSummary:
        """Build category counts from forecast results."""
        return ForecastSummary(
            total_resources=len(results),
            idle=int((results["utilization_category"] == "idle").sum()),
            low_usage=int((results["utilization_category"] == "low_usage").sum()),
            healthy=int((results["utilization_category"] == "healthy").sum()),
            high_usage=int((results["utilization_category"] == "high_usage").sum()),
            waste_high=int((results["waste_probability"] == "high").sum()),
            waste_medium=int((results["waste_probability"] == "medium").sum()),
            waste_low=int((results["waste_probability"] == "low").sum()),
        )

    @staticmethod
    def get_top_waste_candidates(
        results: pd.DataFrame,
        n: int = TOP_N_WASTE,
    ) -> pd.DataFrame:
        """Return top resources by waste probability and lowest forecast CPU."""
        ranked = results.copy()
        ranked["_waste_rank"] = ranked["waste_probability"].map(WASTE_PRIORITY)
        display_columns = [
            "resource_id",
            "resource_type",
            "historical_avg_cpu",
            "forecast_avg_cpu",
            "forecast_min_cpu",
            "forecast_max_cpu",
            "utilization_category",
            "waste_probability",
        ]
        return (
            ranked.sort_values(
                ["_waste_rank", "forecast_avg_cpu", "historical_avg_cpu"],
                ascending=[True, True, True],
            )
            .head(n)[display_columns]
            .reset_index(drop=True)
        )


class ForecastReporter:
    """Format forecast output for console display."""

    @staticmethod
    def print_forecast_summary(summary: ForecastSummary) -> None:
        """Print utilization category summary."""
        print("\n=== FORECAST SUMMARY ===\n")
        print(f"Total Resources: {summary.total_resources}")
        print(f"Idle           : {summary.idle}")
        print(f"Low Usage      : {summary.low_usage}")
        print(f"Healthy        : {summary.healthy}")
        print(f"High Usage     : {summary.high_usage}")
        print()
        print(f"Waste High     : {summary.waste_high}")
        print(f"Waste Medium   : {summary.waste_medium}")
        print(f"Waste Low      : {summary.waste_low}")
        print()

    @staticmethod
    def print_top_waste_candidates(candidates: pd.DataFrame) -> None:
        """Print top waste candidate table."""
        print(f"=== TOP {len(candidates)} WASTE CANDIDATES ===\n")
        print(candidates.to_string(index=False))
        print()


class ForecastVisualizer:
    """Generate matplotlib visualizations for forecast analysis."""

    def __init__(self, figures_dir: Path | None = None) -> None:
        self._figures_dir = figures_dir or workspace_path(MODULE_DIR / "figures")

    def generate_all(
        self,
        historical_data: pd.DataFrame,
        results: pd.DataFrame,
        forecaster: ProphetForecaster,
    ) -> list[Path]:
        """Create and save all required forecast visualizations."""
        self._figures_dir.mkdir(parents=True, exist_ok=True)

        saved = [
            self._plot_actual_vs_forecast(historical_data, results, forecaster),
            self._plot_forecast_trend(results),
            self._plot_waste_probability_distribution(results),
            self._plot_utilization_categories(results),
        ]

        logger.info("Saved %d figure(s) to %s", len(saved), self._figures_dir)
        return saved

    def _plot_actual_vs_forecast(
        self,
        historical_data: pd.DataFrame,
        results: pd.DataFrame,
        forecaster: ProphetForecaster,
    ) -> Path:
        """Plot actual vs forecasted CPU for representative resources."""
        output_path = self._figures_dir / "actual_vs_forecast.png"
        sample_ids = []

        for resource_type in ["healthy", "zombie", "seasonal", "aws", "heuristic_fallback"]:
            matches = results[results["resource_type"] == resource_type]
            if not matches.empty:
                sample_ids.append(matches.iloc[0]["resource_id"])

        if not sample_ids:
            sample_ids = results["resource_id"].head(min(3, len(results))).tolist()

        if not sample_ids:
            output_path = self._figures_dir / "actual_vs_forecast.png"
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, "No forecast samples available", ha="center", va="center")
            ax.axis("off")
            fig.savefig(output_path, dpi=150)
            plt.close(fig)
            return output_path

        fig, axes = plt.subplots(len(sample_ids), 1, figsize=(12, 4 * len(sample_ids)))
        if len(sample_ids) == 1:
            axes = [axes]

        for ax, resource_id in zip(axes, sample_ids, strict=True):
            if historical_data is not None and not historical_data.empty and "resource_id" in historical_data.columns:
                history = historical_data[historical_data["resource_id"] == resource_id].copy()
            else:
                history = pd.DataFrame(columns=["resource_id", "date", "cpu_utilization"])
            forecast = forecaster.get_forecast_detail(resource_id).copy()

            forecast["ds"] = pd.to_datetime(forecast["ds"])

            if not history.empty:
                history["date"] = pd.to_datetime(history["date"])
                ax.plot(
                    history["date"].to_numpy(),
                    history["cpu_utilization"].to_numpy(),
                    label="Actual",
                    color="#2c3e50",
                    linewidth=1.5,
                )
                forecast_start_dt = history["date"].max().to_pydatetime()
            else:
                forecast_start_dt = forecast["ds"].min().to_pydatetime()

            ax.plot(
                forecast["ds"].to_numpy(),
                forecast["yhat"].to_numpy(),
                label="Forecast",
                color="#e74c3c",
                linewidth=1.5,
            )
            ax.fill_between(
                forecast["ds"].to_numpy(),
                forecast["yhat_lower"].clip(0, 100).to_numpy(),
                forecast["yhat_upper"].clip(0, 100).to_numpy(),
                color="#e74c3c",
                alpha=0.15,
            )
            ax.axvline(
                forecast_start_dt,
                color="gray",
                linestyle="--",
                linewidth=1,
                label="Forecast start",
            )
            ax.set_title(f"Actual vs Forecast — {resource_id}")
            ax.set_xlabel("Date")
            ax.set_ylabel("CPU Utilization (%)")
            ax.legend()
            ax.grid(alpha=0.3)

        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_forecast_trend(self, results: pd.DataFrame) -> Path:
        """Plot forecast average CPU distribution by resource type."""
        output_path = self._figures_dir / "forecast_trend.png"
        palette = {
            "healthy": "#2ecc71",
            "zombie": "#e74c3c",
            "seasonal": "#3498db",
            "aws": "#9b59b6",
            "heuristic_fallback": "#f39c12",
        }

        fig, ax = plt.subplots(figsize=(10, 6))
        plotted = False
        for resource_type, color in palette.items():
            subset = results[results["resource_type"] == resource_type]
            if subset.empty:
                continue
            plotted = True
            ax.hist(
                subset["forecast_avg_cpu"],
                bins=max(5, min(20, len(subset))),
                alpha=0.6,
                label=f"{resource_type} (n={len(subset)})",
                color=color,
                edgecolor="white",
            )

        if not plotted:
            ax.hist(
                results["forecast_avg_cpu"],
                bins=max(5, min(20, len(results))),
                alpha=0.6,
                label=f"all (n={len(results)})",
                color="#3498db",
                edgecolor="white",
            )

        ax.set_title("Forecast Average CPU Distribution by Resource Type")
        ax.set_xlabel("Forecast Average CPU (%)")
        ax.set_ylabel("Resource Count")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_waste_probability_distribution(self, results: pd.DataFrame) -> Path:
        """Plot waste probability category counts."""
        output_path = self._figures_dir / "waste_probability_distribution.png"
        counts = results["waste_probability"].value_counts().reindex(
            ["high", "medium", "low"], fill_value=0
        )

        fig, ax = plt.subplots(figsize=(8, 6))
        bars = ax.bar(
            counts.index,
            counts.values,
            color=["#e74c3c", "#f39c12", "#2ecc71"],
            edgecolor="white",
        )
        ax.set_title("Waste Probability Distribution")
        ax.set_xlabel("Waste Probability")
        ax.set_ylabel("Resource Count")

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.5,
                str(int(height)),
                ha="center",
                va="bottom",
                fontweight="bold",
            )

        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_utilization_categories(self, results: pd.DataFrame) -> Path:
        """Plot utilization category counts."""
        output_path = self._figures_dir / "utilization_categories.png"
        order = ["idle", "low_usage", "healthy", "high_usage"]
        counts = results["utilization_category"].value_counts().reindex(order, fill_value=0)

        fig, ax = plt.subplots(figsize=(9, 6))
        bars = ax.bar(
            counts.index,
            counts.values,
            color=["#c0392b", "#e67e22", "#27ae60", "#2980b9"],
            edgecolor="white",
        )
        ax.set_title("Resource Utilization Categories (30-Day Forecast)")
        ax.set_xlabel("Utilization Category")
        ax.set_ylabel("Resource Count")

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.5,
                str(int(height)),
                ha="center",
                va="bottom",
                fontweight="bold",
            )

        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path


class ForecastingPipeline:
    """End-to-end Prophet forecasting workflow."""

    def __init__(
        self,
        data_generator: HistoricalCPUDataGenerator | None = None,
        forecaster: ProphetForecaster | None = None,
        visualizer: ForecastVisualizer | None = None,
        historical_path: Path | None = None,
        results_path: Path | None = None,
        inventory_path: Path | None = None,
    ) -> None:
        self._data_generator = data_generator or HistoricalCPUDataGenerator()
        self._forecaster = forecaster or ProphetForecaster()
        self._visualizer = visualizer or ForecastVisualizer()
        self._historical_path = historical_path or workspace_path(MODULE_DIR / "data" / "historical_cpu_usage.csv")
        self._results_path = results_path or workspace_path(MODULE_DIR / "results" / "forecast_results.csv")
        self._inventory_path = inventory_path or workspace_path(_PROJECT_ROOT / "synthetic_data" / "cloud_resources.csv")

    def run(self) -> pd.DataFrame:
        """Execute generate → forecast → analyze → export → visualize."""
        historical_data = self._data_generator.generate()
        self._data_generator.save(historical_data, self._historical_path)
        return self._run_forecast(historical_data)

    def _load_inventory_baseline(self) -> pd.DataFrame:
        """Load discovered inventory resources from the active scan workspace when available."""
        if not self._inventory_path.exists():
            return pd.DataFrame(columns=["resource_id", "avg_cpu"])
        try:
            inventory = pd.read_csv(self._inventory_path)
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=["resource_id", "avg_cpu"])
        if "resource_id" not in inventory.columns:
            return pd.DataFrame(columns=["resource_id", "avg_cpu"])
        return inventory

    def _build_fallback_forecasts(
        self,
        inventory: pd.DataFrame,
        exclude_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate clearly labelled heuristic fallback forecasts for resources without CloudWatch history."""
        excluded = exclude_ids or set()
        empty_resource_frame = pd.DataFrame(columns=["resource_id", "date", "cpu_utilization", "resource_type"])
        empty_prophet_frame = pd.DataFrame(columns=["ds", "y"])
        rows: list[dict[str, Any]] = []

        if not inventory.empty:
            for _, item in inventory.iterrows():
                resource_id = str(item.get("resource_id") or "").strip()
                if not resource_id or resource_id in excluded:
                    continue
                raw_cpu = item.get("avg_cpu")
                baseline_cpu = 0.0 if raw_cpu is None or pd.isna(raw_cpu) else float(raw_cpu)
                rows.append(
                    self._forecaster._heuristic_forecast(
                        resource_id=resource_id,
                        resource_frame=empty_resource_frame,
                        prophet_frame=empty_prophet_frame,
                        baseline_cpu=baseline_cpu,
                    )
                )
        elif not excluded:
            # Standalone fallback when neither historical data nor inventory exists.
            rows.append(
                self._forecaster._heuristic_forecast(
                    resource_id="res-fallback-0001",
                    resource_frame=empty_resource_frame,
                    prophet_frame=empty_prophet_frame,
                    baseline_cpu=0.0,
                )
            )

        return rows

    def run_from_existing_history(self) -> pd.DataFrame:
        """Forecast using CloudWatch-derived CPU history, falling back to heuristic baselines when unavailable."""
        empty_history = pd.DataFrame(columns=["resource_id", "date", "cpu_utilization", "resource_type"])
        historical_data = empty_history

        if self._historical_path.exists():
            try:
                loaded = pd.read_csv(self._historical_path, parse_dates=["date"])
            except pd.errors.EmptyDataError:
                loaded = empty_history

            if not loaded.empty:
                required = {"resource_id", "date", "cpu_utilization"}
                if not required.issubset(loaded.columns):
                    raise HistoricalDataError(
                        f"Historical data missing columns: {required - set(loaded.columns)}"
                    )
                if "resource_type" not in loaded.columns:
                    loaded = loaded.copy()
                    loaded["resource_type"] = "aws"
                historical_data = loaded
        else:
            logger.warning(
                "Historical CPU data not found at %s — generating heuristic fallback forecasts.",
                self._historical_path,
            )

        if historical_data.empty:
            logger.warning(
                "No CloudWatch CPU history rows available — using heuristic fallback forecast."
            )
            self._historical_path.parent.mkdir(parents=True, exist_ok=True)
            empty_history.to_csv(self._historical_path, index=False)
            inventory = self._load_inventory_baseline()
            fallback_rows = self._build_fallback_forecasts(inventory)
            results = pd.DataFrame(fallback_rows)
            return self._export_and_visualize(historical_data, results)

        logger.info(
            "Using existing CPU history — %d rows across %d resources",
            len(historical_data),
            historical_data["resource_id"].nunique(),
        )
        results = self._forecaster.forecast_all(historical_data)
        inventory = self._load_inventory_baseline()
        extra_rows = self._build_fallback_forecasts(
            inventory,
            exclude_ids=set(results["resource_id"].astype(str).tolist()),
        )
        if extra_rows:
            logger.info(
                "Added %d heuristic fallback forecast(s) for inventory resource(s) without CloudWatch history.",
                len(extra_rows),
            )
            results = pd.concat([results, pd.DataFrame(extra_rows)], ignore_index=True)

        return self._export_and_visualize(historical_data, results)

    def _run_forecast(self, historical_data: pd.DataFrame) -> pd.DataFrame:
        """Train Prophet models and export forecast artifacts."""
        results = self._forecaster.forecast_all(historical_data)
        return self._export_and_visualize(historical_data, results)

    def _export_and_visualize(
        self,
        historical_data: pd.DataFrame,
        results: pd.DataFrame,
    ) -> pd.DataFrame:
        """Export forecast CSV, series cache, and summary figures."""
        series_cache_path = self._results_path.parent / "forecast_series_cache.json"
        self._forecaster.save_series_cache(historical_data, output_path=series_cache_path)
        summary = ForecastAnalyzer.summarize(results)
        top_waste = ForecastAnalyzer.get_top_waste_candidates(results)

        self._results_path.parent.mkdir(parents=True, exist_ok=True)
        export_columns = [
            "resource_id",
            "resource_type",
            "historical_avg_cpu",
            "forecast_avg_cpu",
            "forecast_min_cpu",
            "forecast_max_cpu",
            "utilization_category",
            "waste_probability",
        ]
        results[export_columns].to_csv(self._results_path, index=False)
        logger.info("Forecast results saved to %s", self._results_path)

        figure_paths = self._visualizer.generate_all(
            historical_data=historical_data,
            results=results,
            forecaster=self._forecaster,
        )

        ForecastReporter.print_forecast_summary(summary)
        ForecastReporter.print_top_waste_candidates(top_waste)

        print("=== OUTPUT FILES ===\n")
        print(f"Historical : {self._historical_path}")
        print(f"Results    : {self._results_path}")
        for path in figure_paths:
            print(f"Figure     : {path}")
        print()

        return results


def _configure_logging() -> None:
    """Configure root logging for CLI execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """
    Run the Prophet forecasting pipeline.

    Returns:
        0 on success, 1 on failure.
    """
    _configure_logging()

    try:
        from agents.scout.resource_exporter import is_aws_scan_mode

        pipeline = ForecastingPipeline()
        if is_aws_scan_mode():
            pipeline.run_from_existing_history()
        else:
            pipeline.run()
        return 0
    except HistoricalDataError as exc:
        logger.error("Historical data error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Forecasting pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
