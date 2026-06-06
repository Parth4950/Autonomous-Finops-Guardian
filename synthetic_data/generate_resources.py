"""
Synthetic cloud resource dataset generator.

Produces labeled EC2-like resource records for training and evaluating
Isolation Forest anomaly detection without live AWS dependencies.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SYNTHETIC_DATA_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_CSV = SYNTHETIC_DATA_DIR / "cloud_resources.csv"
DEFAULT_FIGURES_DIR = SYNTHETIC_DATA_DIR / "figures"

RANDOM_SEED = 42


@dataclass(frozen=True)
class ResourceProfile:
    """Statistical bounds for a class of cloud resources."""

    label: str
    count: int
    cpu_min: float
    cpu_max: float
    network_in_min: float
    network_in_max: float
    network_out_min: float
    network_out_max: float
    cost_min: float
    cost_max: float
    id_prefix: str


NORMAL_PROFILE = ResourceProfile(
    label="normal",
    count=500,
    cpu_min=30.0,
    cpu_max=90.0,
    network_in_min=1_000.0,
    network_in_max=100_000.0,
    network_out_min=1_000.0,
    network_out_max=100_000.0,
    cost_min=20.0,
    cost_max=500.0,
    id_prefix="res-normal",
)

ZOMBIE_PROFILE = ResourceProfile(
    label="zombie",
    count=50,
    cpu_min=0.0,
    cpu_max=3.0,
    network_in_min=0.0,
    network_in_max=100.0,
    network_out_min=0.0,
    network_out_max=100.0,
    cost_min=20.0,
    cost_max=500.0,
    id_prefix="res-zombie",
)


class SyntheticResourceGenerator:
    """Generate synthetic cloud resource records from profile definitions."""

    def __init__(self, seed: int = RANDOM_SEED) -> None:
        """
        Initialize the generator with a reproducible random seed.

        Args:
            seed: NumPy random seed for deterministic dataset generation.
        """
        self._rng = np.random.default_rng(seed)

    def generate_profile(self, profile: ResourceProfile) -> list[dict[str, float | str]]:
        """
        Generate resources matching a single profile.

        Args:
            profile: ResourceProfile defining label, count, and value ranges.

        Returns:
            List of resource dictionaries.
        """
        logger.info("Generating %d %s resources...", profile.count, profile.label)

        resources: list[dict[str, float | str]] = []

        for index in range(1, profile.count + 1):
            resources.append(
                {
                    "resource_id": f"{profile.id_prefix}-{index:04d}",
                    "avg_cpu": self._uniform(profile.cpu_min, profile.cpu_max, decimals=2),
                    "avg_network_in": self._uniform(
                        profile.network_in_min, profile.network_in_max, decimals=1
                    ),
                    "avg_network_out": self._uniform(
                        profile.network_out_min, profile.network_out_max, decimals=1
                    ),
                    "monthly_cost": self._uniform(profile.cost_min, profile.cost_max, decimals=2),
                    "resource_label": profile.label,
                }
            )

        return resources

    def generate_dataset(
        self,
        profiles: list[ResourceProfile] | None = None,
    ) -> pd.DataFrame:
        """
        Generate a full labeled dataset across multiple resource profiles.

        Args:
            profiles: List of profiles to generate. Defaults to normal + zombie.

        Returns:
            Combined pandas DataFrame of all generated resources.
        """
        if profiles is None:
            profiles = [NORMAL_PROFILE, ZOMBIE_PROFILE]

        all_resources: list[dict[str, float | str]] = []
        for profile in profiles:
            all_resources.extend(self.generate_profile(profile))

        dataframe = pd.DataFrame(all_resources)
        logger.info("Generated %d total resources", len(dataframe))
        return dataframe

    def _uniform(self, low: float, high: float, decimals: int = 2) -> float:
        """Draw a uniform random value and round to the given decimal places."""
        value = float(self._rng.uniform(low, high))
        return round(value, decimals)


class DatasetExporter:
    """Persist synthetic datasets to disk."""

    def __init__(self, output_path: Path = DEFAULT_OUTPUT_CSV) -> None:
        """
        Initialize the exporter.

        Args:
            output_path: Destination CSV file path.
        """
        self._output_path = output_path

    def save_csv(self, dataframe: pd.DataFrame) -> Path:
        """
        Save a DataFrame to CSV without the pandas index column.

        Args:
            dataframe: Dataset to export.

        Returns:
            Path to the written CSV file.
        """
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(self._output_path, index=False)
        logger.info("Dataset saved to %s", self._output_path)
        return self._output_path


class DatasetStatistics:
    """Compute and display summary statistics for the synthetic dataset."""

    FEATURE_COLUMNS = [
        "avg_cpu",
        "avg_network_in",
        "avg_network_out",
        "monthly_cost",
    ]

    @staticmethod
    def print_summary(dataframe: pd.DataFrame) -> None:
        """
        Print overall and per-label dataset statistics to stdout.

        Args:
            dataframe: Generated resource dataset.
        """
        print("\n=== DATASET STATISTICS ===\n")
        print(f"Total resources : {len(dataframe)}")
        print(f"Normal resources: {(dataframe['resource_label'] == 'normal').sum()}")
        print(f"Zombie resources: {(dataframe['resource_label'] == 'zombie').sum()}")
        print(f"Zombie ratio    : {(dataframe['resource_label'] == 'zombie').mean():.1%}")

        print("\n--- Overall Feature Summary ---")
        print(dataframe[DatasetStatistics.FEATURE_COLUMNS].describe().round(2).to_string())

        print("\n--- Feature Means by Label ---")
        grouped = (
            dataframe.groupby("resource_label")[DatasetStatistics.FEATURE_COLUMNS]
            .mean()
            .round(2)
        )
        print(grouped.to_string())

        print("\n--- Monthly Cost by Label ---")
        cost_summary = (
            dataframe.groupby("resource_label")["monthly_cost"]
            .agg(["count", "mean", "min", "max"])
            .round(2)
        )
        print(cost_summary.to_string())
        print()


class DatasetVisualizer:
    """Generate summary visualizations for the synthetic dataset."""

    def __init__(self, figures_dir: Path = DEFAULT_FIGURES_DIR) -> None:
        """
        Initialize the visualizer.

        Args:
            figures_dir: Directory where PNG figures will be saved.
        """
        self._figures_dir = figures_dir

    def generate_all(self, dataframe: pd.DataFrame) -> list[Path]:
        """
        Create and save all summary visualizations.

        Args:
            dataframe: Generated resource dataset.

        Returns:
            List of paths to saved figure files.
        """
        self._figures_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = [
            self._plot_cpu_distribution(dataframe),
            self._plot_cost_distribution(dataframe),
            self._plot_label_counts(dataframe),
        ]

        logger.info("Saved %d visualization(s) to %s", len(saved_paths), self._figures_dir)
        return saved_paths

    def _plot_cpu_distribution(self, dataframe: pd.DataFrame) -> Path:
        """Plot CPU utilization distribution split by resource label."""
        output_path = self._figures_dir / "cpu_distribution.png"

        fig, ax = plt.subplots(figsize=(10, 6))

        for label, color in [("normal", "#2ecc71"), ("zombie", "#e74c3c")]:
            subset = dataframe[dataframe["resource_label"] == label]
            ax.hist(
                subset["avg_cpu"],
                bins=30,
                alpha=0.65,
                label=f"{label.capitalize()} (n={len(subset)})",
                color=color,
                edgecolor="white",
            )

        ax.set_title("CPU Utilization Distribution — Normal vs Zombie Resources")
        ax.set_xlabel("Average CPU (%)")
        ax.set_ylabel("Resource Count")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)

        return output_path

    def _plot_cost_distribution(self, dataframe: pd.DataFrame) -> Path:
        """Plot monthly cost distribution split by resource label."""
        output_path = self._figures_dir / "cost_distribution.png"

        fig, ax = plt.subplots(figsize=(10, 6))

        for label, color in [("normal", "#3498db"), ("zombie", "#e67e22")]:
            subset = dataframe[dataframe["resource_label"] == label]
            ax.hist(
                subset["monthly_cost"],
                bins=30,
                alpha=0.65,
                label=f"{label.capitalize()} (n={len(subset)})",
                color=color,
                edgecolor="white",
            )

        ax.set_title("Monthly Cost Distribution — Normal vs Zombie Resources")
        ax.set_xlabel("Monthly Cost (USD)")
        ax.set_ylabel("Resource Count")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)

        return output_path

    def _plot_label_counts(self, dataframe: pd.DataFrame) -> Path:
        """Plot bar chart of normal vs zombie resource counts."""
        output_path = self._figures_dir / "label_counts.png"

        label_counts = dataframe["resource_label"].value_counts().sort_index()

        fig, ax = plt.subplots(figsize=(8, 6))
        bars = ax.bar(
            label_counts.index,
            label_counts.values,
            color=["#2ecc71", "#e74c3c"],
            edgecolor="white",
        )

        ax.set_title("Resource Count — Normal vs Zombie")
        ax.set_xlabel("Resource Label")
        ax.set_ylabel("Count")

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 5,
                f"{int(height)}",
                ha="center",
                va="bottom",
                fontweight="bold",
            )

        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)

        return output_path


class SyntheticDatasetPipeline:
    """End-to-end pipeline: generate, export, summarize, and visualize."""

    def __init__(
        self,
        generator: SyntheticResourceGenerator | None = None,
        exporter: DatasetExporter | None = None,
        visualizer: DatasetVisualizer | None = None,
    ) -> None:
        self._generator = generator or SyntheticResourceGenerator()
        self._exporter = exporter or DatasetExporter()
        self._visualizer = visualizer or DatasetVisualizer()

    def run(self) -> pd.DataFrame:
        """
        Execute the full synthetic dataset generation pipeline.

        Returns:
            The generated pandas DataFrame.
        """
        dataframe = self._generator.generate_dataset()
        csv_path = self._exporter.save_csv(dataframe)
        DatasetStatistics.print_summary(dataframe)
        figure_paths = self._visualizer.generate_all(dataframe)

        print("=== OUTPUT FILES ===\n")
        print(f"CSV       : {csv_path}")
        for path in figure_paths:
            print(f"Figure    : {path}")
        print()

        return dataframe


def main() -> int:
    """
    Run the synthetic dataset generator.

    Returns:
        0 on success, 1 on failure.
    """
    try:
        SyntheticDatasetPipeline().run()
        return 0
    except Exception as exc:
        logger.exception("Synthetic dataset generation failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
