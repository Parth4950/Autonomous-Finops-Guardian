"""
Risk Assessor Agent — deterministic risk scoring with Gemini explanations.

Combines waste scores, infrastructure metadata, and rule-based risk evaluation
with AI-generated human-readable assessments.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Allow `python agents/risk_assessor/risk_assessor.py` from any working directory.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.risk_assessor.gemini_explainer import (
    DETERMINISTIC_RECOMMENDATIONS,
    ExplanationResult,
    GeminiExplainer,
    RiskExplanationContext,
)

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = MODULE_DIR / "results"
DEFAULT_FIGURES_DIR = MODULE_DIR / "figures"
DEFAULT_OUTPUT_PATH = DEFAULT_RESULTS_DIR / "risk_assessment.csv"

DEFAULT_FORECAST_PATH = _PROJECT_ROOT / "ml" / "forecasting" / "results" / "forecast_results.csv"

RANDOM_SEED = 42
TOP_N_CANDIDATES = 20

RiskLevel = Literal["low", "medium", "high"]
Environment = Literal["production", "staging", "development"]


@dataclass(frozen=True)
class RiskRuleWeights:
    """Deterministic risk rule point values."""

    production: int = 50
    business_critical: int = 30
    autoscaling_group: int = 20
    load_balancer: int = 15
    recent_activity: int = 10
    owner_exists: int = -10


@dataclass(frozen=True)
class RiskAssessmentSummary:
    """Aggregate risk and recommendation counts."""

    high_risk: int
    medium_risk: int
    low_risk: int
    safe_to_remediate: int
    manual_review_required: int
    do_not_remediate: int
    total_resources: int


class RiskDataError(FileNotFoundError):
    """Raised when required upstream data files are missing."""


class InfrastructureMetadataGenerator:
    """Generate realistic synthetic AWS infrastructure metadata per resource."""

    def __init__(self, seed: int = RANDOM_SEED) -> None:
        self._rng = np.random.default_rng(seed)

    def generate(self, resource_ids: list[str]) -> pd.DataFrame:
        """
        Generate infrastructure metadata for a list of resources.

        Args:
            resource_ids: Resource identifiers (e.g. res-zombie-001).

        Returns:
            DataFrame with infrastructure metadata columns.
        """
        records: list[dict[str, Any]] = []

        for resource_id in resource_ids:
            resource_type = self._parse_resource_type(resource_id)
            records.append(self._generate_record(resource_id, resource_type))

        dataframe = pd.DataFrame(records)
        logger.info("Generated infrastructure metadata for %d resources", len(dataframe))
        return dataframe

    @staticmethod
    def _parse_resource_type(resource_id: str) -> str:
        """Extract resource category from ID (healthy, zombie, seasonal)."""
        parts = resource_id.split("-")
        if len(parts) >= 2:
            return parts[1]
        return "healthy"

    def _generate_record(self, resource_id: str, resource_type: str) -> dict[str, Any]:
        """Generate metadata for a single resource based on its category."""
        if resource_type == "zombie":
            environment = self._weighted_choice(
                ["development", "staging", "production"], [0.65, 0.25, 0.10]
            )
            business_critical = self._rng.random() < 0.05
            attached_to_lb = self._rng.random() < 0.08
            member_of_asg = self._rng.random() < 0.10
            owner_exists = self._rng.random() < 0.40
            recent_activity = int(self._rng.integers(45, 180))
        elif resource_type == "seasonal":
            environment = self._weighted_choice(
                ["staging", "production", "development"], [0.40, 0.40, 0.20]
            )
            business_critical = self._rng.random() < 0.35
            attached_to_lb = self._rng.random() < 0.45
            member_of_asg = self._rng.random() < 0.50
            owner_exists = self._rng.random() < 0.75
            recent_activity = int(self._rng.integers(1, 21))
        else:
            environment = self._weighted_choice(
                ["production", "staging", "development"], [0.50, 0.30, 0.20]
            )
            business_critical = self._rng.random() < 0.45
            attached_to_lb = self._rng.random() < 0.40
            member_of_asg = self._rng.random() < 0.35
            owner_exists = self._rng.random() < 0.80
            recent_activity = int(self._rng.integers(1, 45))

        return {
            "resource_id": resource_id,
            "environment": environment,
            "business_critical": business_critical,
            "attached_to_load_balancer": attached_to_lb,
            "member_of_autoscaling_group": member_of_asg,
            "owner_exists": owner_exists,
            "recent_activity_days": recent_activity,
        }

    def _weighted_choice(self, options: list[str], weights: list[float]) -> str:
        """Select a value using weighted random choice."""
        return str(self._rng.choice(options, p=weights))


class WasteScoreEngine:
    """Derive numeric waste scores from Prophet forecast outputs."""

    WASTE_PROBABILITY_WEIGHTS: dict[str, float] = {
        "high": 1.0,
        "medium": 0.65,
        "low": 0.25,
    }

    @classmethod
    def compute_waste_score(
        cls,
        forecast_avg_cpu: float,
        waste_probability: str,
    ) -> float:
        """
        Compute a 0-100 waste score from forecast utilization and waste probability.

        Lower utilization and higher waste probability produce higher scores.
        """
        utilization_waste = max(0.0, min(100.0, 100.0 - forecast_avg_cpu * 1.25))
        weight = cls.WASTE_PROBABILITY_WEIGHTS.get(waste_probability, 0.5)
        score = utilization_waste * weight

        if waste_probability == "high":
            score = max(score, 75.0)

        return round(min(100.0, score), 1)

    @classmethod
    def enrich_forecast_data(cls, forecast_df: pd.DataFrame) -> pd.DataFrame:
        """Add waste_score and synthetic monthly_cost to forecast results."""
        enriched = forecast_df.copy()
        enriched["waste_score"] = enriched.apply(
            lambda row: cls.compute_waste_score(
                row["forecast_avg_cpu"],
                row["waste_probability"],
            ),
            axis=1,
        )
        enriched["monthly_cost"] = enriched["resource_id"].apply(
            cls._estimate_monthly_cost
        )
        return enriched

    @staticmethod
    def _estimate_monthly_cost(resource_id: str) -> float:
        """Estimate monthly cost based on resource category."""
        resource_type = resource_id.split("-")[1] if "-" in resource_id else "healthy"
        cost_ranges = {
            "zombie": (25.0, 120.0),
            "seasonal": (80.0, 350.0),
            "healthy": (50.0, 500.0),
        }
        low, high = cost_ranges.get(resource_type, (50.0, 300.0))
        rng = np.random.default_rng(hash(resource_id) % (2**32))
        return round(float(rng.uniform(low, high)), 2)


class RiskAssessor:
    """
    Deterministic risk rules engine.

    Computes risk scores exclusively from infrastructure metadata and
    operational context — never from ML model outputs directly.
    """

    def __init__(self, weights: RiskRuleWeights | None = None) -> None:
        self._weights = weights or RiskRuleWeights()

    @staticmethod
    def classify_risk_level(risk_score: int) -> RiskLevel:
        """
        Map a numeric risk score to a risk level category.

        Args:
            risk_score: Score from 0 to 100.

        Returns:
            low (0-39), medium (40-79), or high (80-100).
        """
        if risk_score >= 80:
            return "high"
        if risk_score >= 40:
            return "medium"
        return "low"

    def calculate_risk_score(self, metadata: dict[str, Any]) -> int:
        """
        Apply deterministic risk rules to infrastructure metadata.

        Rules:
            Production environment: +50
            Business critical: +30
            Auto Scaling Group member: +20
            Load balancer attached: +15
            Recent activity < 30 days: +10
            Owner exists: -10

        Args:
            metadata: Dictionary with infrastructure metadata fields.

        Returns:
            Risk score clamped to 0-100.
        """
        score = 0

        if metadata.get("environment") == "production":
            score += self._weights.production

        if metadata.get("business_critical"):
            score += self._weights.business_critical

        if metadata.get("member_of_autoscaling_group"):
            score += self._weights.autoscaling_group

        if metadata.get("attached_to_load_balancer"):
            score += self._weights.load_balancer

        if metadata.get("recent_activity_days", 999) < 30:
            score += self._weights.recent_activity

        if metadata.get("owner_exists"):
            score += self._weights.owner_exists

        return max(0, min(100, score))

    def assess(self, enriched_forecast: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
        """
        Produce risk scores for all resources.

        Args:
            enriched_forecast: Forecast data with waste_score and monthly_cost.
            metadata: Infrastructure metadata per resource.

        Returns:
            DataFrame with risk_score and risk_level columns.
        """
        merged = enriched_forecast.merge(metadata, on="resource_id", how="inner")

        risk_scores: list[int] = []
        risk_levels: list[str] = []

        for _, row in merged.iterrows():
            score = self.calculate_risk_score(row.to_dict())
            risk_scores.append(score)
            risk_levels.append(self.classify_risk_level(score))

        merged["risk_score"] = risk_scores
        merged["risk_level"] = risk_levels

        logger.info(
            "Risk assessment complete — low: %d, medium: %d, high: %d",
            risk_levels.count("low"),
            risk_levels.count("medium"),
            risk_levels.count("high"),
        )
        return merged


class RiskAssessmentReporter:
    """Format and print risk assessment summaries."""

    @staticmethod
    def summarize(results: pd.DataFrame) -> RiskAssessmentSummary:
        """Compute aggregate counts from assessment results."""
        return RiskAssessmentSummary(
            total_resources=len(results),
            high_risk=int((results["risk_level"] == "high").sum()),
            medium_risk=int((results["risk_level"] == "medium").sum()),
            low_risk=int((results["risk_level"] == "low").sum()),
            safe_to_remediate=int(
                (results["recommendation"] == "Safe To Remediate").sum()
            ),
            manual_review_required=int(
                (results["recommendation"] == "Manual Review Required").sum()
            ),
            do_not_remediate=int(
                (results["recommendation"] == "Do Not Remediate").sum()
            ),
        )

    @staticmethod
    def get_remediation_candidates(
        results: pd.DataFrame,
        n: int = TOP_N_CANDIDATES,
    ) -> pd.DataFrame:
        """
        Return top resources with high waste and low risk — ideal remediation targets.

        Sorted by waste_score descending, filtered to low risk and safe recommendation.
        """
        candidates = results[
            (results["risk_level"] == "low")
            & (results["recommendation"] == "Safe To Remediate")
        ].copy()

        display_columns = [
            "resource_id",
            "waste_score",
            "risk_score",
            "risk_level",
            "monthly_cost",
            "waste_probability",
            "recommendation",
            "risk_explanation",
        ]

        if candidates.empty:
            return candidates

        return (
            candidates.sort_values("waste_score", ascending=False)
            .head(n)[display_columns]
            .reset_index(drop=True)
        )

    @staticmethod
    def get_high_waste_low_risk(
        results: pd.DataFrame,
        n: int = TOP_N_CANDIDATES,
    ) -> pd.DataFrame:
        """Return top resources by waste score where risk is low."""
        filtered = results[results["risk_level"] == "low"].copy()
        return (
            filtered.sort_values(["waste_score", "risk_score"], ascending=[False, True])
            .head(n)
            .reset_index(drop=True)
        )

    @staticmethod
    def print_summary(summary: RiskAssessmentSummary) -> None:
        """Print risk assessment summary to stdout."""
        print("\n=== RISK ASSESSMENT SUMMARY ===\n")
        print(f"High Risk              : {summary.high_risk}")
        print(f"Medium Risk            : {summary.medium_risk}")
        print(f"Low Risk               : {summary.low_risk}")
        print()
        print(f"Safe To Remediate      : {summary.safe_to_remediate}")
        print(f"Manual Review Required : {summary.manual_review_required}")
        print(f"Do Not Remediate       : {summary.do_not_remediate}")
        print()

    @staticmethod
    def print_remediation_candidates(candidates: pd.DataFrame) -> None:
        """Print top remediation candidates table."""
        print(f"=== TOP {min(TOP_N_CANDIDATES, len(candidates))} REMEDIATION CANDIDATES ===\n")
        if candidates.empty:
            print("No safe remediation candidates found.")
        else:
            print(
                candidates[
                    [
                        "resource_id",
                        "waste_score",
                        "risk_score",
                        "risk_level",
                        "monthly_cost",
                        "recommendation",
                    ]
                ].to_string(index=False)
            )
        print()


class RiskAssessmentVisualizer:
    """Generate matplotlib visualizations for risk assessment analytics."""

    def __init__(self, figures_dir: Path = DEFAULT_FIGURES_DIR) -> None:
        self._figures_dir = figures_dir

    def generate_all(self, results: pd.DataFrame) -> list[Path]:
        """Create and save all required visualizations."""
        self._figures_dir.mkdir(parents=True, exist_ok=True)

        top_candidates = RiskAssessmentReporter.get_high_waste_low_risk(results)

        saved = [
            self._plot_risk_distribution(results),
            self._plot_waste_vs_risk_scatter(results),
            self._plot_recommendation_distribution(results),
            self._plot_top_remediation_candidates(top_candidates),
        ]

        logger.info("Saved %d figure(s) to %s", len(saved), self._figures_dir)
        return saved

    def _plot_risk_distribution(self, results: pd.DataFrame) -> Path:
        """Plot risk level distribution bar chart."""
        output_path = self._figures_dir / "risk_distribution.png"
        order = ["low", "medium", "high"]
        counts = results["risk_level"].value_counts().reindex(order, fill_value=0)

        fig, ax = plt.subplots(figsize=(8, 6))
        bars = ax.bar(
            counts.index,
            counts.values,
            color=["#2ecc71", "#f39c12", "#e74c3c"],
            edgecolor="white",
        )
        ax.set_title("Risk Level Distribution")
        ax.set_xlabel("Risk Level")
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

    def _plot_waste_vs_risk_scatter(self, results: pd.DataFrame) -> Path:
        """Plot waste score vs risk score scatter colored by risk level."""
        output_path = self._figures_dir / "waste_vs_risk_scatter.png"
        palette = {"low": "#2ecc71", "medium": "#f39c12", "high": "#e74c3c"}

        fig, ax = plt.subplots(figsize=(10, 7))
        for level, color in palette.items():
            subset = results[results["risk_level"] == level]
            ax.scatter(
                subset["waste_score"],
                subset["risk_score"],
                alpha=0.7,
                s=50,
                label=f"{level} (n={len(subset)})",
                color=color,
                edgecolors="white",
                linewidths=0.3,
            )

        ax.set_title("Waste Score vs Risk Score")
        ax.set_xlabel("Waste Score")
        ax.set_ylabel("Risk Score")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_recommendation_distribution(self, results: pd.DataFrame) -> Path:
        """Plot operational recommendation counts."""
        output_path = self._figures_dir / "recommendation_distribution.png"
        order = [
            "Safe To Remediate",
            "Manual Review Required",
            "Do Not Remediate",
        ]
        counts = results["recommendation"].value_counts().reindex(order, fill_value=0)

        fig, ax = plt.subplots(figsize=(9, 6))
        bars = ax.bar(
            range(len(order)),
            counts.values,
            color=["#27ae60", "#f39c12", "#c0392b"],
            edgecolor="white",
        )
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(order, rotation=15, ha="right")
        ax.set_title("Operational Recommendation Distribution")
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

    def _plot_top_remediation_candidates(self, candidates: pd.DataFrame) -> Path:
        """Plot top high-waste low-risk remediation candidates."""
        output_path = self._figures_dir / "top_remediation_candidates.png"

        if candidates.empty:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, "No remediation candidates", ha="center", va="center")
            ax.axis("off")
            fig.savefig(output_path, dpi=150)
            plt.close(fig)
            return output_path

        plot_data = candidates.head(TOP_N_CANDIDATES).sort_values(
            "waste_score", ascending=True
        )

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.barh(
            plot_data["resource_id"],
            plot_data["waste_score"],
            color="#27ae60",
            edgecolor="white",
        )
        ax.set_title("Top 20 High Waste + Low Risk Resources")
        ax.set_xlabel("Waste Score")
        ax.set_ylabel("Resource ID")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path


class RiskAssessmentPipeline:
    """
    End-to-end Risk Assessor Agent pipeline.

    Waste Score → Infrastructure Metadata → Risk Rules → Gemini Explanation
    """

    def __init__(
        self,
        forecast_path: Path = DEFAULT_FORECAST_PATH,
        output_path: Path = DEFAULT_OUTPUT_PATH,
        metadata_generator: InfrastructureMetadataGenerator | None = None,
        risk_assessor: RiskAssessor | None = None,
        explainer: GeminiExplainer | None = None,
        visualizer: RiskAssessmentVisualizer | None = None,
    ) -> None:
        self._forecast_path = forecast_path
        self._output_path = output_path
        self._metadata_generator = metadata_generator or InfrastructureMetadataGenerator()
        self._risk_assessor = risk_assessor or RiskAssessor()
        self._explainer = explainer or GeminiExplainer()
        self._visualizer = visualizer or RiskAssessmentVisualizer()

    def load_forecast_data(self) -> pd.DataFrame:
        """Load Prophet forecast results."""
        if not self._forecast_path.exists():
            raise RiskDataError(
                f"Forecast results not found at {self._forecast_path}. "
                "Run ml/forecasting/prophet_forecaster.py first."
            )
        return pd.read_csv(self._forecast_path)

    def _attach_explanations(self, assessed: pd.DataFrame) -> pd.DataFrame:
        """Call Gemini (or fallback) to generate explanations for each resource."""
        explanations: list[str] = []
        recommendations: list[str] = []
        sources: list[str] = []

        contexts = [
            RiskExplanationContext(
                resource_id=row["resource_id"],
                environment=row["environment"],
                business_critical=bool(row["business_critical"]),
                attached_to_load_balancer=bool(row["attached_to_load_balancer"]),
                member_of_autoscaling_group=bool(row["member_of_autoscaling_group"]),
                owner_exists=bool(row["owner_exists"]),
                recent_activity_days=int(row["recent_activity_days"]),
                waste_score=float(row["waste_score"]),
                monthly_cost=float(row["monthly_cost"]),
                waste_probability=str(row["waste_probability"]),
                risk_score=int(row["risk_score"]),
                risk_level=str(row["risk_level"]),
            )
            for _, row in assessed.iterrows()
        ]

        logger.info(
            "Generating explanations for %d resources (Gemini available: %s)...",
            len(contexts),
            self._explainer.is_gemini_available,
        )

        explanation_results: list[ExplanationResult] = self._explainer.explain_batch(
            contexts
        )

        for result in explanation_results:
            explanations.append(result.risk_explanation)
            recommendations.append(result.recommendation)
            sources.append(result.source)

        assessed = assessed.copy()
        assessed["risk_explanation"] = explanations
        assessed["recommendation"] = recommendations
        assessed["explanation_source"] = sources
        return assessed

    def run(self) -> pd.DataFrame:
        """Execute the full risk assessment pipeline."""
        forecast_df = self.load_forecast_data()
        enriched = WasteScoreEngine.enrich_forecast_data(forecast_df)

        metadata = self._metadata_generator.generate(
            resource_ids=enriched["resource_id"].tolist()
        )

        assessed = self._risk_assessor.assess(enriched, metadata)
        final = self._attach_explanations(assessed)

        export_columns = [
            "resource_id",
            "waste_score",
            "monthly_cost",
            "waste_probability",
            "environment",
            "business_critical",
            "attached_to_load_balancer",
            "member_of_autoscaling_group",
            "owner_exists",
            "recent_activity_days",
            "risk_score",
            "risk_level",
            "risk_explanation",
            "recommendation",
        ]

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        final[export_columns].to_csv(self._output_path, index=False)
        logger.info("Risk assessment saved to %s", self._output_path)

        figure_paths = self._visualizer.generate_all(final)
        summary = RiskAssessmentReporter.summarize(final)
        candidates = RiskAssessmentReporter.get_remediation_candidates(final)

        RiskAssessmentReporter.print_summary(summary)
        RiskAssessmentReporter.print_remediation_candidates(candidates)

        gemini_count = int((final["explanation_source"] == "gemini").sum())
        fallback_count = int((final["explanation_source"] == "fallback").sum())
        print(f"Explanations via Gemini : {gemini_count}")
        print(f"Explanations via Fallback: {fallback_count}")
        print()

        print("=== OUTPUT FILES ===\n")
        print(f"Assessment : {self._output_path}")
        for path in figure_paths:
            print(f"Figure     : {path}")
        print()

        return final


def _configure_logging() -> None:
    """Configure root logging for CLI execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """
    Run the Risk Assessor Agent pipeline.

    Returns:
        0 on success, 1 on failure.
    """
    _configure_logging()

    try:
        RiskAssessmentPipeline().run()
        return 0
    except RiskDataError as exc:
        logger.error("Data error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Risk assessment pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
