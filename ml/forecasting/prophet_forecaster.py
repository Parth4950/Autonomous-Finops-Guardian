"""
Prophet-based CPU utilization forecasting for cloud FinOps waste detection.

Generates synthetic historical utilization, trains per-resource Prophet models,
classifies forecast trends, and estimates waste probability.
"""

from __future__ import annotations

import logging
import sys
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

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

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = MODULE_DIR / "data"
DEFAULT_RESULTS_DIR = MODULE_DIR / "results"
DEFAULT_FIGURES_DIR = MODULE_DIR / "figures"
DEFAULT_HISTORICAL_PATH = DEFAULT_DATA_DIR / "historical_cpu_usage.csv"
DEFAULT_FORECAST_RESULTS_PATH = DEFAULT_RESULTS_DIR / "forecast_results.csv"

RANDOM_SEED = 42
HISTORY_DAYS = 90
FORECAST_DAYS = 30
TOTAL_RESOURCES = 100
TOP_N_WASTE = 20

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
        historical_avg_cpu = round(float(prophet_frame["y"].mean()), 2)

        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
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

        utilization_category = self.classify_utilization(forecast_avg_cpu)
        waste_probability = self.classify_waste_probability(
            historical_avg_cpu=historical_avg_cpu,
            forecast_avg_cpu=forecast_avg_cpu,
        )

        return {
            "resource_id": resource_id,
            "resource_type": resource_frame["resource_type"].iloc[0],
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
        logger.info("Forecasting complete for %d resources", len(results_frame))
        return results_frame

    def get_forecast_detail(self, resource_id: str) -> pd.DataFrame:
        """Return full Prophet forecast DataFrame for a resource."""
        if resource_id not in self._forecast_details:
            raise KeyError(f"No forecast detail stored for resource: {resource_id}")
        return self._forecast_details[resource_id]


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

    def __init__(self, figures_dir: Path = DEFAULT_FIGURES_DIR) -> None:
        self._figures_dir = figures_dir

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

        for resource_type in ["healthy", "zombie", "seasonal"]:
            matches = results[results["resource_type"] == resource_type]
            if not matches.empty:
                sample_ids.append(matches.iloc[0]["resource_id"])

        fig, axes = plt.subplots(len(sample_ids), 1, figsize=(12, 4 * len(sample_ids)))
        if len(sample_ids) == 1:
            axes = [axes]

        for ax, resource_id in zip(axes, sample_ids, strict=True):
            history = historical_data[historical_data["resource_id"] == resource_id].copy()
            forecast = forecaster.get_forecast_detail(resource_id).copy()

            history["date"] = pd.to_datetime(history["date"])
            forecast["ds"] = pd.to_datetime(forecast["ds"])

            ax.plot(
                history["date"].to_numpy(),
                history["cpu_utilization"].to_numpy(),
                label="Actual",
                color="#2c3e50",
                linewidth=1.5,
            )
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
                history["date"].max().to_pydatetime(),
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
        palette = {"healthy": "#2ecc71", "zombie": "#e74c3c", "seasonal": "#3498db"}

        fig, ax = plt.subplots(figsize=(10, 6))
        for resource_type, color in palette.items():
            subset = results[results["resource_type"] == resource_type]
            ax.hist(
                subset["forecast_avg_cpu"],
                bins=20,
                alpha=0.6,
                label=f"{resource_type} (n={len(subset)})",
                color=color,
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
        historical_path: Path = DEFAULT_HISTORICAL_PATH,
        results_path: Path = DEFAULT_FORECAST_RESULTS_PATH,
    ) -> None:
        self._data_generator = data_generator or HistoricalCPUDataGenerator()
        self._forecaster = forecaster or ProphetForecaster()
        self._visualizer = visualizer or ForecastVisualizer()
        self._historical_path = historical_path
        self._results_path = results_path

    def run(self) -> pd.DataFrame:
        """Execute generate → forecast → analyze → export → visualize."""
        historical_data = self._data_generator.generate()
        self._data_generator.save(historical_data, self._historical_path)

        results = self._forecaster.forecast_all(historical_data)
        summary = ForecastAnalyzer.summarize(results)
        top_waste = ForecastAnalyzer.get_top_waste_candidates(results)

        self._results_path.parent.mkdir(parents=True, exist_ok=True)
        export_columns = [
            "resource_id",
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
        ForecastingPipeline().run()
        return 0
    except HistoricalDataError as exc:
        logger.error("Historical data error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Forecasting pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
