"""
Isolation Forest anomaly detector for cloud resource waste detection.

Trains on utilization and cost features, scores resources for anomalous
behavior, and evaluates performance against labeled synthetic data.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import StandardScaler

# Allow `python ml/isolation_forest/isolation_detector.py` from any directory.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET_PATH = _PROJECT_ROOT / "synthetic_data" / "cloud_resources.csv"
DEFAULT_RESULTS_DIR = MODULE_DIR / "results"
DEFAULT_FIGURES_DIR = MODULE_DIR / "figures"
DEFAULT_PREDICTIONS_PATH = DEFAULT_RESULTS_DIR / "predictions.csv"

FEATURE_COLUMNS: list[str] = [
    "avg_cpu",
    "avg_network_in",
    "avg_network_out",
    "monthly_cost",
]

RANDOM_SEED = 42
CONTAMINATION = 0.09
TOP_N_SUSPICIOUS = 20


@dataclass(frozen=True)
class EvaluationMetrics:
    """Classification metrics comparing predictions to ground-truth labels."""

    accuracy: float
    precision: float
    recall: float
    f1_score: float
    confusion_matrix: np.ndarray
    classification_report: str

    def to_dict(self) -> dict[str, float]:
        """Return scalar metrics as a dictionary."""
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
        }


@dataclass(frozen=True)
class FinOpsSummary:
    """Operational summary of anomaly detection results."""

    total_resources: int
    normal_resources: int
    zombie_resources: int
    detected_anomalies: int
    missed_zombies: int
    false_positives: int


class DatasetLoadError(FileNotFoundError):
    """Raised when the training dataset cannot be loaded."""


class IsolationForestDetector:
    """
    Detect anomalous cloud resources using Isolation Forest.

    Loads labeled synthetic data, standardizes features, trains an
    IsolationForest model, and produces predictions with anomaly scores.
    """

    def __init__(
        self,
        contamination: float = CONTAMINATION,
        random_state: int = RANDOM_SEED,
    ) -> None:
        """
        Initialize the detector.

        Args:
            contamination: Expected proportion of anomalies in the dataset.
            random_state: Random seed for reproducible model training.
        """
        self._contamination = contamination
        self._random_state = random_state
        self._scaler = StandardScaler()
        self._model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )
        self._dataframe: pd.DataFrame | None = None
        self._results: pd.DataFrame | None = None
        self._metrics: EvaluationMetrics | None = None
        self._finops_summary: FinOpsSummary | None = None

    @property
    def results(self) -> pd.DataFrame:
        """Return the latest prediction results DataFrame."""
        if self._results is None:
            raise RuntimeError("Detector has not been fit and run yet.")
        return self._results

    @property
    def metrics(self) -> EvaluationMetrics:
        """Return evaluation metrics from the latest run."""
        if self._metrics is None:
            raise RuntimeError("Detector has not been evaluated yet.")
        return self._metrics

    @property
    def finops_summary(self) -> FinOpsSummary:
        """Return the FinOps operational summary from the latest run."""
        if self._finops_summary is None:
            raise RuntimeError("FinOps summary has not been computed yet.")
        return self._finops_summary

    def load_dataset(self, dataset_path: Path = DEFAULT_DATASET_PATH) -> pd.DataFrame:
        """
        Load the synthetic cloud resource dataset from CSV.

        Args:
            dataset_path: Path to ``cloud_resources.csv``.

        Returns:
            Loaded pandas DataFrame.

        Raises:
            DatasetLoadError: If the file is missing or malformed.
        """
        if not dataset_path.exists():
            raise DatasetLoadError(
                f"Dataset not found at {dataset_path}. "
                "Run synthetic_data/generate_resources.py first."
            )

        try:
            dataframe = pd.read_csv(dataset_path)
        except Exception as exc:
            raise DatasetLoadError(f"Failed to read dataset: {exc}") from exc

        missing_columns = set(FEATURE_COLUMNS + ["resource_id", "resource_label"]) - set(
            dataframe.columns
        )
        if missing_columns:
            raise DatasetLoadError(
                f"Dataset is missing required columns: {', '.join(sorted(missing_columns))}"
            )

        self._dataframe = dataframe
        logger.info("Loaded %d resources from %s", len(dataframe), dataset_path)
        return dataframe

    def _extract_features(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Return the feature matrix used for model training and inference."""
        return dataframe[FEATURE_COLUMNS].copy()

    @staticmethod
    def _prediction_to_label(prediction: int) -> str:
        """Map Isolation Forest prediction integers to human-readable labels."""
        return "anomaly" if prediction == -1 else "normal"

    @staticmethod
    def _build_ground_truth(dataframe: pd.DataFrame) -> np.ndarray:
        """
        Build binary ground-truth array where zombie resources are anomalies.

        Returns:
            1 for zombie (anomaly), 0 for normal.
        """
        return (dataframe["resource_label"] == "zombie").astype(int).to_numpy()

    @staticmethod
    def _build_predicted_labels(predictions: np.ndarray) -> np.ndarray:
        """
        Build binary prediction array from Isolation Forest output.

        Returns:
            1 for predicted anomaly (-1), 0 for predicted normal (1).
        """
        return (predictions == -1).astype(int)

    def fit_predict(self, dataframe: pd.DataFrame | None = None) -> pd.DataFrame:
        """
        Standardize features, train the model, and generate predictions.

        Args:
            dataframe: Optional pre-loaded DataFrame. Loads default CSV if None.

        Returns:
            DataFrame with prediction, anomaly_score, and prediction_label columns.

        Raises:
            DatasetLoadError: If no data is available to train on.
        """
        if dataframe is None:
            if self._dataframe is None:
                self.load_dataset()
            dataframe = self._dataframe

        if dataframe is None or dataframe.empty:
            raise DatasetLoadError("Cannot train on an empty dataset.")

        features = self._extract_features(dataframe)
        scaled_features = self._scaler.fit_transform(features)

        logger.info(
            "Training Isolation Forest (contamination=%.2f, seed=%d)...",
            self._contamination,
            self._random_state,
        )
        self._model.fit(scaled_features)

        predictions = self._model.predict(scaled_features)
        anomaly_scores = self._model.decision_function(scaled_features)

        results = dataframe.copy()
        results["prediction"] = predictions
        results["anomaly_score"] = anomaly_scores.round(4)
        results["prediction_label"] = [
            self._prediction_to_label(int(value)) for value in predictions
        ]

        self._results = results
        logger.info(
            "Predictions complete — %d anomalies detected",
            (results["prediction"] == -1).sum(),
        )
        return results

    def evaluate(self, results: pd.DataFrame | None = None) -> EvaluationMetrics:
        """
        Compare model predictions against ground-truth resource labels.

        Args:
            results: Prediction DataFrame. Uses cached results if None.

        Returns:
            EvaluationMetrics with accuracy, precision, recall, and F1.
        """
        if results is None:
            results = self.results

        y_true = self._build_ground_truth(results)
        y_pred = self._build_predicted_labels(results["prediction"].to_numpy())

        metrics = EvaluationMetrics(
            accuracy=accuracy_score(y_true, y_pred),
            precision=precision_score(y_true, y_pred, zero_division=0),
            recall=recall_score(y_true, y_pred, zero_division=0),
            f1_score=f1_score(y_true, y_pred, zero_division=0),
            confusion_matrix=confusion_matrix(y_true, y_pred),
            classification_report=classification_report(
                y_true,
                y_pred,
                target_names=["normal", "anomaly"],
                zero_division=0,
            ),
        )

        self._metrics = metrics
        self._finops_summary = self._compute_finops_summary(results)
        return metrics

    def _compute_finops_summary(self, results: pd.DataFrame) -> FinOpsSummary:
        """Compute operational FinOps counters from prediction results."""
        actual_zombie = results["resource_label"] == "zombie"
        actual_normal = results["resource_label"] == "normal"
        predicted_anomaly = results["prediction"] == -1
        predicted_normal = results["prediction"] == 1

        return FinOpsSummary(
            total_resources=len(results),
            normal_resources=int(actual_normal.sum()),
            zombie_resources=int(actual_zombie.sum()),
            detected_anomalies=int(predicted_anomaly.sum()),
            missed_zombies=int((actual_zombie & predicted_normal).sum()),
            false_positives=int((actual_normal & predicted_anomaly).sum()),
        )

    def get_top_suspicious(self, n: int = TOP_N_SUSPICIOUS) -> pd.DataFrame:
        """
        Return the most suspicious resources sorted by lowest anomaly score.

        Lower anomaly scores indicate greater isolation — stronger anomaly signal.

        Args:
            n: Number of top suspicious resources to return.

        Returns:
            DataFrame sorted ascending by anomaly_score.
        """
        display_columns = [
            "resource_id",
            "anomaly_score",
            "avg_cpu",
            "avg_network_in",
            "avg_network_out",
            "monthly_cost",
            "resource_label",
            "prediction_label",
        ]
        return (
            self.results[display_columns]
            .sort_values("anomaly_score", ascending=True)
            .head(n)
            .reset_index(drop=True)
        )

    def save_predictions(
        self,
        results: pd.DataFrame | None = None,
        output_path: Path = DEFAULT_PREDICTIONS_PATH,
    ) -> Path:
        """
        Persist prediction results to CSV.

        Args:
            results: Prediction DataFrame. Uses cached results if None.
            output_path: Destination CSV path.

        Returns:
            Path to the saved CSV file.
        """
        if results is None:
            results = self.results

        output_path.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(output_path, index=False)
        logger.info("Predictions saved to %s", output_path)
        return output_path


class ResultReporter:
    """Format and print model performance and FinOps summaries."""

    @staticmethod
    def print_model_performance(metrics: EvaluationMetrics) -> None:
        """Print classification metrics to stdout."""
        print("\n=== MODEL PERFORMANCE ===\n")
        print(f"Accuracy : {metrics.accuracy:.4f}")
        print(f"Precision: {metrics.precision:.4f}")
        print(f"Recall   : {metrics.recall:.4f}")
        print(f"F1 Score : {metrics.f1_score:.4f}")
        print("\nConfusion Matrix (rows=actual, cols=predicted):")
        print("              Predicted Normal  Predicted Anomaly")
        print(f"Actual Normal      {metrics.confusion_matrix[0][0]:>6}          {metrics.confusion_matrix[0][1]:>6}")
        print(f"Actual Anomaly     {metrics.confusion_matrix[1][0]:>6}          {metrics.confusion_matrix[1][1]:>6}")
        print("\nClassification Report:")
        print(metrics.classification_report)

    @staticmethod
    def print_top_suspicious(top_resources: pd.DataFrame) -> None:
        """Print the top suspicious resources table."""
        print(f"\n=== TOP {len(top_resources)} MOST SUSPICIOUS RESOURCES ===\n")
        print(top_resources.to_string(index=False))

    @staticmethod
    def print_finops_analysis(summary: FinOpsSummary) -> None:
        """Print operational FinOps counters."""
        print("\n=== FINOPS ANALYSIS ===\n")
        print(f"Total Resources   : {summary.total_resources}")
        print(f"Normal Resources  : {summary.normal_resources}")
        print(f"Zombie Resources  : {summary.zombie_resources}")
        print(f"Detected Anomalies: {summary.detected_anomalies}")
        print(f"Missed Zombies    : {summary.missed_zombies}")
        print(f"False Positives   : {summary.false_positives}")
        print()


class ResultVisualizer:
    """Generate matplotlib visualizations for anomaly detection results."""

    def __init__(self, figures_dir: Path = DEFAULT_FIGURES_DIR) -> None:
        self._figures_dir = figures_dir

    def generate_all(
        self,
        results: pd.DataFrame,
        metrics: EvaluationMetrics,
        top_suspicious: pd.DataFrame,
    ) -> list[Path]:
        """
        Create and save all required visualizations.

        Returns:
            List of paths to saved figure files.
        """
        self._figures_dir.mkdir(parents=True, exist_ok=True)

        saved = [
            self._plot_confusion_matrix(metrics),
            self._plot_anomaly_score_distribution(results),
            self._plot_cpu_vs_network_scatter(results),
            self._plot_top_suspicious(top_suspicious),
        ]

        logger.info("Saved %d figure(s) to %s", len(saved), self._figures_dir)
        return saved

    def _plot_confusion_matrix(self, metrics: EvaluationMetrics) -> Path:
        """Plot confusion matrix as a heatmap."""
        output_path = self._figures_dir / "confusion_matrix.png"
        matrix = metrics.confusion_matrix

        fig, ax = plt.subplots(figsize=(8, 6))
        image = ax.imshow(matrix, cmap="Blues")

        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["Predicted Normal", "Predicted Anomaly"])
        ax.set_yticklabels(["Actual Normal", "Actual Anomaly"])
        ax.set_title("Confusion Matrix — Isolation Forest")

        for row in range(matrix.shape[0]):
            for col in range(matrix.shape[1]):
                ax.text(
                    col,
                    row,
                    str(matrix[row, col]),
                    ha="center",
                    va="center",
                    color="white" if matrix[row, col] > matrix.max() / 2 else "black",
                    fontweight="bold",
                    fontsize=14,
                )

        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_anomaly_score_distribution(self, results: pd.DataFrame) -> Path:
        """Plot anomaly score distributions by actual resource label."""
        output_path = self._figures_dir / "anomaly_score_distribution.png"

        fig, ax = plt.subplots(figsize=(10, 6))

        for label, color in [("normal", "#2ecc71"), ("zombie", "#e74c3c")]:
            subset = results[results["resource_label"] == label]
            ax.hist(
                subset["anomaly_score"],
                bins=30,
                alpha=0.65,
                label=f"{label.capitalize()} (n={len(subset)})",
                color=color,
                edgecolor="white",
            )

        ax.axvline(x=0, color="black", linestyle="--", linewidth=1, label="Decision boundary (0)")
        ax.set_title("Anomaly Score Distribution by Actual Label")
        ax.set_xlabel("Anomaly Score (lower = more suspicious)")
        ax.set_ylabel("Resource Count")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_cpu_vs_network_scatter(self, results: pd.DataFrame) -> Path:
        """Plot CPU vs Network In colored by actual and predicted labels."""
        output_path = self._figures_dir / "cpu_vs_network_scatter.png"

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        actual_palette = {"normal": "#2ecc71", "zombie": "#e74c3c"}
        predicted_palette = {"normal": "#3498db", "anomaly": "#e67e22"}

        for label, color in actual_palette.items():
            subset = results[results["resource_label"] == label]
            axes[0].scatter(
                subset["avg_cpu"],
                subset["avg_network_in"],
                alpha=0.6,
                s=30,
                label=f"{label} (n={len(subset)})",
                color=color,
                edgecolors="white",
                linewidths=0.3,
            )

        axes[0].set_title("CPU vs Network In — Actual Label")
        axes[0].set_xlabel("Average CPU (%)")
        axes[0].set_ylabel("Average Network In (bytes)")
        axes[0].legend()
        axes[0].grid(alpha=0.3)

        for label, color in predicted_palette.items():
            subset = results[results["prediction_label"] == label]
            axes[1].scatter(
                subset["avg_cpu"],
                subset["avg_network_in"],
                alpha=0.6,
                s=30,
                label=f"{label} (n={len(subset)})",
                color=color,
                edgecolors="white",
                linewidths=0.3,
            )

        axes[1].set_title("CPU vs Network In — Predicted Label")
        axes[1].set_xlabel("Average CPU (%)")
        axes[1].set_ylabel("Average Network In (bytes)")
        axes[1].legend()
        axes[1].grid(alpha=0.3)

        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_top_suspicious(self, top_suspicious: pd.DataFrame) -> Path:
        """Plot horizontal bar chart of top suspicious resources."""
        output_path = self._figures_dir / "top_suspicious_resources.png"

        plot_data = top_suspicious.sort_values("anomaly_score", ascending=True)
        colors = [
            "#e74c3c" if label == "zombie" else "#95a5a6"
            for label in plot_data["resource_label"]
        ]

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.barh(
            plot_data["resource_id"],
            plot_data["anomaly_score"],
            color=colors,
            edgecolor="white",
        )
        ax.set_title(f"Top {len(plot_data)} Most Suspicious Resources")
        ax.set_xlabel("Anomaly Score (lower = more suspicious)")
        ax.set_ylabel("Resource ID")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path


class AnomalyDetectionPipeline:
    """End-to-end pipeline: load, train, evaluate, export, and visualize."""

    def __init__(
        self,
        detector: IsolationForestDetector | None = None,
        visualizer: ResultVisualizer | None = None,
        dataset_path: Path = DEFAULT_DATASET_PATH,
        predictions_path: Path = DEFAULT_PREDICTIONS_PATH,
    ) -> None:
        self._detector = detector or IsolationForestDetector()
        self._visualizer = visualizer or ResultVisualizer()
        self._dataset_path = dataset_path
        self._predictions_path = predictions_path

    def run(self) -> pd.DataFrame:
        """
        Execute the full anomaly detection workflow.

        Returns:
            DataFrame with predictions and anomaly scores.
        """
        self._detector.load_dataset(self._dataset_path)
        results = self._detector.fit_predict()
        metrics = self._detector.evaluate(results)
        top_suspicious = self._detector.get_top_suspicious()
        predictions_path = self._detector.save_predictions(
            results=results,
            output_path=self._predictions_path,
        )
        figure_paths = self._visualizer.generate_all(
            results=results,
            metrics=metrics,
            top_suspicious=top_suspicious,
        )

        ResultReporter.print_model_performance(metrics)
        ResultReporter.print_top_suspicious(top_suspicious)
        ResultReporter.print_finops_analysis(self._detector.finops_summary)

        print("=== OUTPUT FILES ===\n")
        print(f"Predictions : {predictions_path}")
        for path in figure_paths:
            print(f"Figure      : {path}")
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
    Run the Isolation Forest anomaly detection pipeline.

    Returns:
        0 on success, 1 on failure.
    """
    _configure_logging()

    try:
        AnomalyDetectionPipeline().run()
        return 0
    except DatasetLoadError as exc:
        logger.error("Dataset error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Anomaly detection pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
