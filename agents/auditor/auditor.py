"""
Auditor Agent — financial waste analysis and executive cost reporting.

Transforms risk assessments into dollar-denominated savings opportunities
and generates executive-level FinOps reports.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.auditor.gemini_reporter import ExecutiveReport, GeminiReporter

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = MODULE_DIR / "results"
DEFAULT_FIGURES_DIR = MODULE_DIR / "figures"
DEFAULT_OUTPUT_PATH = DEFAULT_RESULTS_DIR / "audit_results.csv"
DEFAULT_REPORT_PATH = DEFAULT_RESULTS_DIR / "executive_report.json"
DEFAULT_RISK_ASSESSMENT_PATH = (
    _PROJECT_ROOT / "agents" / "risk_assessor" / "results" / "risk_assessment.csv"
)

TOP_N_OPPORTUNITIES = 20

SAVINGS_RATES: dict[str, float] = {
    "Safe To Remediate": 1.0,
    "Manual Review Required": 0.5,
    "Do Not Remediate": 0.0,
}

RISK_PRIORITY_BONUS: dict[str, float] = {
    "low": 20.0,
    "medium": 10.0,
    "high": 0.0,
}

PriorityCategory = Literal[
    "Critical Savings Opportunity",
    "High Savings Opportunity",
    "Medium Savings Opportunity",
    "Low Savings Opportunity",
]


class AuditDataError(FileNotFoundError):
    """Raised when required upstream data is missing."""


@dataclass(frozen=True)
class AuditSummary:
    """Aggregate financial audit metrics."""

    total_resources: int
    total_monthly_cost: float
    total_annual_cost: float
    potential_monthly_savings: float
    potential_annual_savings: float
    safe_to_remediate: int
    manual_review_required: int
    do_not_remediate: int


class Auditor:
    """
    Financial cost analysis engine for cloud resource waste.

    Calculates annual costs, potential savings, and priority scores
    from risk assessment outputs.
    """

    @staticmethod
    def parse_resource_type(resource_id: str) -> str:
        """Extract resource category from resource ID (e.g. res-zombie-001 → zombie)."""
        parts = resource_id.split("-")
        return parts[1] if len(parts) >= 2 else "unknown"

    @staticmethod
    def calculate_savings_rate(recommendation: str) -> float:
        """
        Return the savings capture rate for a recommendation category.

        Safe To Remediate: 100%, Manual Review: 50%, Do Not Remediate: 0%.
        """
        return SAVINGS_RATES.get(recommendation, 0.0)

    @staticmethod
    def calculate_priority_score(
        waste_score: float,
        monthly_cost: float,
        risk_level: str,
        max_monthly_cost: float,
    ) -> float:
        """
        Compute a 0-100 priority score for savings remediation.

        Factors: waste_score (50%), monthly_cost normalized (30%), low-risk bonus (20%).
        """
        waste_component = min(50.0, waste_score * 0.5)
        cost_normalized = (monthly_cost / max(max_monthly_cost, 1.0)) * 30.0
        risk_bonus = RISK_PRIORITY_BONUS.get(risk_level, 0.0)
        score = waste_component + cost_normalized + risk_bonus
        return round(min(100.0, max(0.0, score)), 1)

    @staticmethod
    def classify_priority(score: float) -> PriorityCategory:
        """Map priority score to a savings opportunity category."""
        if score >= 80:
            return "Critical Savings Opportunity"
        if score >= 60:
            return "High Savings Opportunity"
        if score >= 40:
            return "Medium Savings Opportunity"
        return "Low Savings Opportunity"

    def analyze(self, risk_data: pd.DataFrame) -> pd.DataFrame:
        """
        Run full cost analysis on risk assessment data.

        Args:
            risk_data: DataFrame from Risk Assessor output.

        Returns:
            Audit results with cost, savings, and priority columns.
        """
        required = {
            "resource_id",
            "monthly_cost",
            "waste_score",
            "risk_level",
            "recommendation",
        }
        missing = required - set(risk_data.columns)
        if missing:
            raise ValueError(f"Risk data missing columns: {', '.join(sorted(missing))}")

        results = risk_data.copy()
        results["resource_type"] = results["resource_id"].apply(self.parse_resource_type)
        results["annual_cost"] = (results["monthly_cost"] * 12).round(2)

        savings_rates = results["recommendation"].apply(self.calculate_savings_rate)
        results["potential_monthly_savings"] = (
            results["monthly_cost"] * savings_rates
        ).round(2)
        results["potential_annual_savings"] = (
            results["potential_monthly_savings"] * 12
        ).round(2)

        max_cost = float(results["monthly_cost"].max())
        results["priority_score"] = results.apply(
            lambda row: self.calculate_priority_score(
                waste_score=float(row["waste_score"]),
                monthly_cost=float(row["monthly_cost"]),
                risk_level=str(row["risk_level"]),
                max_monthly_cost=max_cost,
            ),
            axis=1,
        )
        results["priority_category"] = results["priority_score"].apply(
            self.classify_priority
        )

        logger.info(
            "Audit analysis complete — potential monthly savings: $%.2f",
            results["potential_monthly_savings"].sum(),
        )
        return results


class AuditReporter:
    """Format and print audit summaries."""

    @staticmethod
    def summarize(results: pd.DataFrame) -> AuditSummary:
        """Compute aggregate audit metrics."""
        return AuditSummary(
            total_resources=len(results),
            total_monthly_cost=float(results["monthly_cost"].sum()),
            total_annual_cost=float(results["annual_cost"].sum()),
            potential_monthly_savings=float(results["potential_monthly_savings"].sum()),
            potential_annual_savings=float(results["potential_annual_savings"].sum()),
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
    def get_top_opportunities(
        results: pd.DataFrame,
        n: int = TOP_N_OPPORTUNITIES,
    ) -> pd.DataFrame:
        """Return top resources ranked by potential monthly savings."""
        columns = [
            "resource_id",
            "resource_type",
            "monthly_cost",
            "waste_score",
            "risk_level",
            "priority_score",
            "priority_category",
            "potential_monthly_savings",
            "potential_annual_savings",
            "recommendation",
        ]
        return (
            results.sort_values("potential_monthly_savings", ascending=False)
            .head(n)[columns]
            .reset_index(drop=True)
        )

    @staticmethod
    def print_summary(summary: AuditSummary) -> None:
        """Print audit summary to stdout."""
        print("\n=== AUDIT SUMMARY ===\n")
        print(f"Total Resources         : {summary.total_resources}")
        print(f"Total Monthly Cost      : ${summary.total_monthly_cost:,.2f}")
        print(f"Total Annual Cost       : ${summary.total_annual_cost:,.2f}")
        print()
        print(f"Potential Monthly Savings: ${summary.potential_monthly_savings:,.2f}")
        print(f"Potential Annual Savings : ${summary.potential_annual_savings:,.2f}")
        print()
        print(f"Safe To Remediate       : {summary.safe_to_remediate}")
        print(f"Manual Review Required  : {summary.manual_review_required}")
        print(f"Do Not Remediate        : {summary.do_not_remediate}")
        print()

    @staticmethod
    def print_top_opportunities(opportunities: pd.DataFrame) -> None:
        """Print top savings opportunities table."""
        print(f"=== TOP {len(opportunities)} SAVINGS OPPORTUNITIES ===\n")
        if opportunities.empty:
            print("No savings opportunities identified.")
        else:
            print(opportunities.to_string(index=False))
        print()

    @staticmethod
    def print_executive_report(report: ExecutiveReport) -> None:
        """Print executive report sections to stdout."""
        print("=== EXECUTIVE REPORT ===\n")
        print(f"Source: {report.source}\n")
        print("Executive Summary:")
        print(report.executive_summary)
        print()

        sections = [
            ("Key Findings", report.key_findings),
            ("Top Cost Drivers", report.top_cost_drivers),
            ("Recommended Actions", report.recommended_actions),
            ("Risk Considerations", report.risk_considerations),
        ]
        for title, items in sections:
            print(f"{title}:")
            for item in items:
                print(f"  - {item}")
            print()

        savings = report.estimated_savings
        print("Estimated Savings:")
        print(f"  Monthly: ${savings.get('monthly_usd', 0):,.2f}")
        print(f"  Annual : ${savings.get('annual_usd', 0):,.2f}")
        print()


class AuditVisualizer:
    """Generate financial audit visualizations."""

    def __init__(self, figures_dir: Path = DEFAULT_FIGURES_DIR) -> None:
        self._figures_dir = figures_dir

    def generate_all(self, results: pd.DataFrame) -> list[Path]:
        """Create and save all audit visualizations."""
        self._figures_dir.mkdir(parents=True, exist_ok=True)

        saved = [
            self._plot_monthly_waste_distribution(results),
            self._plot_annual_savings_distribution(results),
            self._plot_priority_score_distribution(results),
            self._plot_top_costliest_waste(results),
            self._plot_savings_by_recommendation(results),
        ]

        logger.info("Saved %d figure(s) to %s", len(saved), self._figures_dir)
        return saved

    def _plot_monthly_waste_distribution(self, results: pd.DataFrame) -> Path:
        """Plot distribution of potential monthly savings."""
        output_path = self._figures_dir / "monthly_waste_distribution.png"

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(
            results["potential_monthly_savings"],
            bins=25,
            color="#3498db",
            edgecolor="white",
            alpha=0.8,
        )
        ax.set_title("Monthly Waste (Potential Savings) Distribution")
        ax.set_xlabel("Potential Monthly Savings (USD)")
        ax.set_ylabel("Resource Count")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_annual_savings_distribution(self, results: pd.DataFrame) -> Path:
        """Plot distribution of potential annual savings."""
        output_path = self._figures_dir / "annual_savings_distribution.png"

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(
            results["potential_annual_savings"],
            bins=25,
            color="#2ecc71",
            edgecolor="white",
            alpha=0.8,
        )
        ax.set_title("Annual Savings Distribution")
        ax.set_xlabel("Potential Annual Savings (USD)")
        ax.set_ylabel("Resource Count")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_priority_score_distribution(self, results: pd.DataFrame) -> Path:
        """Plot priority score distribution by category."""
        output_path = self._figures_dir / "priority_score_distribution.png"
        order = [
            "Critical Savings Opportunity",
            "High Savings Opportunity",
            "Medium Savings Opportunity",
            "Low Savings Opportunity",
        ]
        counts = results["priority_category"].value_counts().reindex(order, fill_value=0)
        colors = ["#c0392b", "#e67e22", "#f1c40f", "#95a5a6"]

        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(range(len(order)), counts.values, color=colors, edgecolor="white")
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels([c.replace(" Savings Opportunity", "") for c in order], rotation=15)
        ax.set_title("Priority Score Category Distribution")
        ax.set_ylabel("Resource Count")

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.3,
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

    def _plot_top_costliest_waste(self, results: pd.DataFrame) -> Path:
        """Plot top 20 costliest waste resources by potential savings."""
        output_path = self._figures_dir / "top_costliest_waste.png"
        top = results.nlargest(TOP_N_OPPORTUNITIES, "potential_monthly_savings").sort_values(
            "potential_monthly_savings", ascending=True
        )

        fig, ax = plt.subplots(figsize=(10, 8))
        colors = [
            "#27ae60" if r == "Safe To Remediate" else "#f39c12" if r == "Manual Review Required" else "#c0392b"
            for r in top["recommendation"]
        ]
        ax.barh(top["resource_id"], top["potential_monthly_savings"], color=colors, edgecolor="white")
        ax.set_title("Top 20 Costliest Waste Resources")
        ax.set_xlabel("Potential Monthly Savings (USD)")
        ax.set_ylabel("Resource ID")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_savings_by_recommendation(self, results: pd.DataFrame) -> Path:
        """Plot total potential savings grouped by recommendation."""
        output_path = self._figures_dir / "savings_by_recommendation.png"
        grouped = (
            results.groupby("recommendation")["potential_monthly_savings"]
            .sum()
            .reindex(
                ["Safe To Remediate", "Manual Review Required", "Do Not Remediate"],
                fill_value=0,
            )
        )

        fig, ax = plt.subplots(figsize=(9, 6))
        bars = ax.bar(
            range(len(grouped)),
            grouped.values,
            color=["#27ae60", "#f39c12", "#c0392b"],
            edgecolor="white",
        )
        ax.set_xticks(range(len(grouped)))
        ax.set_xticklabels(grouped.index, rotation=15, ha="right")
        ax.set_title("Potential Monthly Savings by Recommendation Category")
        ax.set_ylabel("Total Potential Monthly Savings (USD)")

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 5,
                f"${height:,.0f}",
                ha="center",
                va="bottom",
                fontweight="bold",
            )

        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path


class AuditorPipeline:
    """End-to-end Auditor Agent workflow."""

    def __init__(
        self,
        risk_assessment_path: Path = DEFAULT_RISK_ASSESSMENT_PATH,
        output_path: Path = DEFAULT_OUTPUT_PATH,
        report_path: Path = DEFAULT_REPORT_PATH,
        auditor: Auditor | None = None,
        reporter: GeminiReporter | None = None,
        visualizer: AuditVisualizer | None = None,
    ) -> None:
        self._risk_path = risk_assessment_path
        self._output_path = output_path
        self._report_path = report_path
        self._auditor = auditor or Auditor()
        self._gemini_reporter = reporter or GeminiReporter()
        self._visualizer = visualizer or AuditVisualizer()

    def load_risk_assessment(self) -> pd.DataFrame:
        """Load Risk Assessor output CSV."""
        if not self._risk_path.exists():
            raise AuditDataError(
                f"Risk assessment not found at {self._risk_path}. "
                "Run agents/risk_assessor/risk_assessor.py first."
            )
        return pd.read_csv(self._risk_path)

    def run(self) -> pd.DataFrame:
        """Execute the full audit pipeline."""
        risk_data = self.load_risk_assessment()
        results = self._auditor.analyze(risk_data)

        export_columns = [
            "resource_id",
            "resource_type",
            "monthly_cost",
            "annual_cost",
            "waste_score",
            "risk_level",
            "priority_score",
            "priority_category",
            "potential_monthly_savings",
            "potential_annual_savings",
            "recommendation",
        ]

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        results[export_columns].to_csv(self._output_path, index=False)
        logger.info("Audit results saved to %s", self._output_path)

        executive_report = self._gemini_reporter.generate_report(results)
        self._report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._report_path, "w", encoding="utf-8") as handle:
            json.dump(executive_report.to_dict(), handle, indent=2)
        logger.info("Executive report saved to %s", self._report_path)

        figure_paths = self._visualizer.generate_all(results)
        summary = AuditReporter.summarize(results)
        opportunities = AuditReporter.get_top_opportunities(results)

        AuditReporter.print_summary(summary)
        AuditReporter.print_top_opportunities(opportunities)
        AuditReporter.print_executive_report(executive_report)

        print("=== OUTPUT FILES ===\n")
        print(f"Audit CSV  : {self._output_path}")
        print(f"Report JSON: {self._report_path}")
        for path in figure_paths:
            print(f"Figure     : {path}")
        print()

        return results


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """Run the Auditor Agent pipeline."""
    _configure_logging()

    try:
        AuditorPipeline().run()
        return 0
    except AuditDataError as exc:
        logger.error("Data error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Auditor pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
