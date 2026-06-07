"""
Planner Agent — deterministic remediation planning with Gemini justifications.

Transforms risk assessments and financial audits into actionable remediation
plans with human-reviewable approval packages.
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

from agents.planner.gemini_planner import (
    GeminiPlanner,
    PlanningContext,
    PlanningJustification,
    RemediationAction,
)

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = MODULE_DIR / "results"
DEFAULT_FIGURES_DIR = MODULE_DIR / "figures"
DEFAULT_OUTPUT_PATH = DEFAULT_RESULTS_DIR / "remediation_plan.csv"
DEFAULT_APPROVAL_PATH = DEFAULT_RESULTS_DIR / "approval_packages.json"

DEFAULT_AUDIT_PATH = _PROJECT_ROOT / "agents" / "auditor" / "results" / "audit_results.csv"
DEFAULT_RISK_PATH = _PROJECT_ROOT / "agents" / "risk_assessor" / "results" / "risk_assessment.csv"

TOP_N_PLANS = 20

RiskLevel = Literal["low", "medium", "high"]

EXECUTION_STEP_TEMPLATES: dict[RemediationAction, list[str]] = {
    "snapshot_and_delete": [
        "Create snapshot",
        "Verify snapshot success",
        "Delete EBS volume",
    ],
    "terminate": [
        "Create backup",
        "Verify backup",
        "Terminate instance",
    ],
    "resize": [
        "Stop instance",
        "Modify instance type",
        "Restart instance",
    ],
    "stop": [
        "Stop instance",
        "Verify stopped state",
        "Notify resource owner",
    ],
    "manual_review": [
        "Flag resource for manual review",
        "Notify stakeholders",
        "Await approval decision",
    ],
    "ignore": [
        "No action required",
        "Continue monitoring",
        "Re-evaluate on next assessment cycle",
    ],
}

ACTION_DISPLAY_LABELS: dict[str, str] = {
    "terminate": "Terminate",
    "resize": "Resize",
    "stop": "Stop",
    "snapshot_and_delete": "Snapshot & Delete",
    "manual_review": "Manual Review",
    "ignore": "Ignore",
}


class PlannerDataError(FileNotFoundError):
    """Raised when required upstream data is missing."""


@dataclass(frozen=True)
class ApprovalPackage:
    """Human-reviewable remediation package for the dashboard."""

    resource_id: str
    action: RemediationAction
    risk_level: str
    estimated_savings: float
    business_justification: str
    execution_steps: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "action": self.action,
            "risk_level": self.risk_level,
            "estimated_savings": self.estimated_savings,
            "business_justification": self.business_justification,
            "execution_steps": self.execution_steps,
        }


@dataclass(frozen=True)
class PlannerSummary:
    """Aggregate remediation planning metrics."""

    terminate: int
    resize: int
    stop: int
    snapshot_and_delete: int
    manual_review: int
    ignore: int
    total_estimated_savings: float


class Planner:
    """
    Deterministic remediation decision engine.

    Selects remediation actions based on resource type, waste score,
    and risk level — never delegating decisions to AI.
    """

    @staticmethod
    def normalize_resource_type(resource_id: str, resource_type: str) -> str:
        """
        Normalize resource type for planning rules.

        Supports AWS types (ebs, ec2) and synthetic categories
        (healthy, zombie, seasonal).
        """
        lowered_id = resource_id.lower()
        lowered_type = resource_type.lower()

        if lowered_type == "ebs" or "ebs" in lowered_id:
            return "ebs"
        if lowered_type in ("ec2", "instance", "compute"):
            return "ec2"
        return lowered_type

    @staticmethod
    def determine_action(
        resource_id: str,
        resource_type: str,
        waste_score: float,
        risk_level: str,
    ) -> RemediationAction:
        """
        Apply deterministic remediation rules.

        Rules are evaluated in priority order — resource-specific and
        risk-level gates take precedence over waste-score thresholds.
        """
        normalized_type = Planner.normalize_resource_type(resource_id, resource_type)
        level = risk_level.lower().strip()

        if level == "high":
            return "ignore"

        if level == "medium":
            return "manual_review"

        if normalized_type == "ebs" and level == "low":
            return "snapshot_and_delete"

        if level == "low" and waste_score > 80:
            return "terminate"

        if level == "low" and 50 <= waste_score <= 80:
            return "resize"

        return "ignore"

    @staticmethod
    def generate_execution_steps(action: RemediationAction) -> list[str]:
        """Return ordered execution steps for a remediation action."""
        return list(EXECUTION_STEP_TEMPLATES[action])

    @staticmethod
    def calculate_estimated_savings(
        action: RemediationAction,
        potential_annual_savings: float,
    ) -> float:
        """Compute estimated savings based on action type."""
        if action == "ignore":
            return 0.0
        if action == "manual_review":
            return round(potential_annual_savings * 0.5, 2)
        if action == "resize":
            return round(potential_annual_savings * 0.6, 2)
        if action == "stop":
            return round(potential_annual_savings * 0.8, 2)
        return round(potential_annual_savings, 2)

    def plan_resource(self, row: pd.Series) -> dict[str, Any]:
        """
        Generate a remediation plan for a single resource.

        Args:
            row: Merged audit and risk assessment record.

        Returns:
            Dictionary with action, steps, and savings fields.
        """
        action = self.determine_action(
            resource_id=str(row["resource_id"]),
            resource_type=str(row["resource_type"]),
            waste_score=float(row["waste_score"]),
            risk_level=str(row["risk_level"]),
        )
        execution_steps = self.generate_execution_steps(action)
        estimated_savings = self.calculate_estimated_savings(
            action,
            float(row["potential_annual_savings"]),
        )

        return {
            "action": action,
            "execution_steps": execution_steps,
            "estimated_savings": estimated_savings,
        }

    def plan_all(self, merged_data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate remediation plans for all resources.

        Args:
            merged_data: Combined audit and risk assessment DataFrame.

        Returns:
            DataFrame with action, execution steps, and savings columns.
        """
        required = {
            "resource_id",
            "resource_type",
            "waste_score",
            "risk_level",
            "potential_annual_savings",
        }
        missing = required - set(merged_data.columns)
        if missing:
            raise ValueError(f"Input data missing columns: {', '.join(sorted(missing))}")

        results = merged_data.copy()
        plan_outputs = results.apply(self.plan_resource, axis=1, result_type="expand")
        results = pd.concat([results, plan_outputs], axis=1)

        logger.info(
            "Remediation planning complete — %d resources planned",
            len(results),
        )
        return results


class PlannerReporter:
    """Format and print planner summaries."""

    @staticmethod
    def summarize(results: pd.DataFrame) -> PlannerSummary:
        """Compute aggregate action counts and savings."""
        action_counts = results["action"].value_counts()
        return PlannerSummary(
            terminate=int(action_counts.get("terminate", 0)),
            resize=int(action_counts.get("resize", 0)),
            stop=int(action_counts.get("stop", 0)),
            snapshot_and_delete=int(action_counts.get("snapshot_and_delete", 0)),
            manual_review=int(action_counts.get("manual_review", 0)),
            ignore=int(action_counts.get("ignore", 0)),
            total_estimated_savings=float(results["estimated_savings"].sum()),
        )

    @staticmethod
    def get_top_plans(
        results: pd.DataFrame,
        n: int = TOP_N_PLANS,
    ) -> pd.DataFrame:
        """Return top remediation plans ranked by estimated savings."""
        columns = [
            "resource_id",
            "resource_type",
            "action",
            "risk_level",
            "waste_score",
            "estimated_savings",
            "business_justification",
        ]
        return (
            results.sort_values("estimated_savings", ascending=False)
            .head(n)[columns]
            .reset_index(drop=True)
        )

    @staticmethod
    def print_summary(summary: PlannerSummary) -> None:
        """Print planner summary to stdout."""
        print("\n=== PLANNER SUMMARY ===\n")
        print(f"Terminate          : {summary.terminate}")
        print(f"Resize             : {summary.resize}")
        print(f"Stop               : {summary.stop}")
        print(f"Snapshot & Delete  : {summary.snapshot_and_delete}")
        print(f"Manual Review      : {summary.manual_review}")
        print(f"Ignore             : {summary.ignore}")
        print()
        print(f"Total Estimated Savings: ${summary.total_estimated_savings:,.2f}")
        print()

    @staticmethod
    def print_top_plans(plans: pd.DataFrame) -> None:
        """Print top remediation plans table."""
        print(f"=== TOP {len(plans)} REMEDIATION PLANS ===\n")
        if plans.empty:
            print("No remediation plans generated.")
        else:
            display = plans.copy()
            display["action"] = display["action"].map(
                lambda value: ACTION_DISPLAY_LABELS.get(str(value), str(value))
            )
            print(display.to_string(index=False))
        print()


class PlannerVisualizer:
    """Generate remediation planning visualizations."""

    def __init__(self, figures_dir: Path = DEFAULT_FIGURES_DIR) -> None:
        self._figures_dir = figures_dir

    def generate_all(self, results: pd.DataFrame) -> list[Path]:
        """Create and save all planner visualizations."""
        self._figures_dir.mkdir(parents=True, exist_ok=True)

        saved = [
            self._plot_action_distribution(results),
            self._plot_savings_by_action(results),
            self._plot_risk_level_by_action(results),
            self._plot_top_impact_plans(results),
        ]

        logger.info("Saved %d figure(s) to %s", len(saved), self._figures_dir)
        return saved

    def _plot_action_distribution(self, results: pd.DataFrame) -> Path:
        """Plot count of resources by remediation action."""
        output_path = self._figures_dir / "action_distribution.png"
        order = list(EXECUTION_STEP_TEMPLATES.keys())
        counts = results["action"].value_counts().reindex(order, fill_value=0)
        labels = [ACTION_DISPLAY_LABELS.get(action, action) for action in order]
        colors = ["#c0392b", "#e67e22", "#3498db", "#9b59b6", "#f39c12", "#95a5a6"]

        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(range(len(order)), counts.values, color=colors, edgecolor="white")
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_title("Remediation Action Distribution")
        ax.set_ylabel("Resource Count")

        for bar in bars:
            height = bar.get_height()
            if height > 0:
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

    def _plot_savings_by_action(self, results: pd.DataFrame) -> Path:
        """Plot total estimated savings grouped by action."""
        output_path = self._figures_dir / "savings_by_action.png"
        grouped = (
            results.groupby("action")["estimated_savings"]
            .sum()
            .reindex(list(EXECUTION_STEP_TEMPLATES.keys()), fill_value=0)
        )
        labels = [
            ACTION_DISPLAY_LABELS.get(action, action) for action in grouped.index
        ]
        colors = ["#c0392b", "#e67e22", "#3498db", "#9b59b6", "#f39c12", "#95a5a6"]

        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(range(len(grouped)), grouped.values, color=colors, edgecolor="white")
        ax.set_xticks(range(len(grouped)))
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_title("Estimated Savings by Remediation Action")
        ax.set_ylabel("Total Estimated Annual Savings (USD)")

        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + 50,
                    f"${height:,.0f}",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                    fontsize=8,
                )

        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_risk_level_by_action(self, results: pd.DataFrame) -> Path:
        """Plot risk level distribution within each action."""
        output_path = self._figures_dir / "risk_level_by_action.png"
        pivot = pd.crosstab(results["action"], results["risk_level"])
        for level in ("low", "medium", "high"):
            if level not in pivot.columns:
                pivot[level] = 0
        pivot = pivot[["low", "medium", "high"]]
        pivot = pivot.reindex(list(EXECUTION_STEP_TEMPLATES.keys()), fill_value=0)

        labels = [
            ACTION_DISPLAY_LABELS.get(action, action) for action in pivot.index
        ]
        x = np.arange(len(labels))
        width = 0.25
        colors = {"low": "#27ae60", "medium": "#f39c12", "high": "#c0392b"}

        fig, ax = plt.subplots(figsize=(11, 6))
        for index, level in enumerate(["low", "medium", "high"]):
            offset = (index - 1) * width
            ax.bar(
                x + offset,
                pivot[level].values,
                width,
                label=level.capitalize(),
                color=colors[level],
                edgecolor="white",
            )

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_title("Risk Level by Remediation Action")
        ax.set_ylabel("Resource Count")
        ax.legend(title="Risk Level")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path

    def _plot_top_impact_plans(self, results: pd.DataFrame) -> Path:
        """Plot top 20 highest-impact remediation plans."""
        output_path = self._figures_dir / "top_impact_plans.png"
        top = results.nlargest(TOP_N_PLANS, "estimated_savings").sort_values(
            "estimated_savings", ascending=True
        )
        action_colors = {
            "terminate": "#c0392b",
            "resize": "#e67e22",
            "stop": "#3498db",
            "snapshot_and_delete": "#9b59b6",
            "manual_review": "#f39c12",
            "ignore": "#95a5a6",
        }
        colors = [action_colors.get(action, "#34495e") for action in top["action"]]

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.barh(top["resource_id"], top["estimated_savings"], color=colors, edgecolor="white")
        ax.set_title("Top 20 Highest Impact Remediation Plans")
        ax.set_xlabel("Estimated Annual Savings (USD)")
        ax.set_ylabel("Resource ID")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path


class PlannerPipeline:
    """End-to-end Planner Agent workflow."""

    def __init__(
        self,
        audit_path: Path = DEFAULT_AUDIT_PATH,
        risk_path: Path = DEFAULT_RISK_PATH,
        output_path: Path = DEFAULT_OUTPUT_PATH,
        approval_path: Path = DEFAULT_APPROVAL_PATH,
        planner: Planner | None = None,
        gemini_planner: GeminiPlanner | None = None,
        visualizer: PlannerVisualizer | None = None,
    ) -> None:
        self._audit_path = audit_path
        self._risk_path = risk_path
        self._output_path = output_path
        self._approval_path = approval_path
        self._planner = planner or Planner()
        self._gemini_planner = gemini_planner or GeminiPlanner()
        self._visualizer = visualizer or PlannerVisualizer()

    def load_inputs(self) -> pd.DataFrame:
        """Load and merge Auditor and Risk Assessor outputs."""
        if not self._audit_path.exists():
            raise PlannerDataError(
                f"Audit results not found at {self._audit_path}. "
                "Run agents/auditor/auditor.py first."
            )
        if not self._risk_path.exists():
            raise PlannerDataError(
                f"Risk assessment not found at {self._risk_path}. "
                "Run agents/risk_assessor/risk_assessor.py first."
            )

        audit_data = pd.read_csv(self._audit_path)
        risk_data = pd.read_csv(self._risk_path)

        risk_columns = [
            "resource_id",
            "risk_score",
            "environment",
            "business_critical",
            "attached_to_load_balancer",
            "member_of_autoscaling_group",
            "owner_exists",
            "recent_activity_days",
            "risk_explanation",
        ]
        merged = audit_data.merge(
            risk_data[risk_columns],
            on="resource_id",
            how="left",
        )

        logger.info("Loaded %d resources for remediation planning", len(merged))
        return merged

    @staticmethod
    def _format_execution_steps(steps: list[str]) -> str:
        """Serialize execution steps for CSV export."""
        return " | ".join(steps)

    @staticmethod
    def _parse_execution_steps(steps_value: Any) -> list[str]:
        """Deserialize execution steps from plan output."""
        if isinstance(steps_value, list):
            return steps_value
        return [step.strip() for step in str(steps_value).split("|")]

    def _build_planning_contexts(self, results: pd.DataFrame) -> list[PlanningContext]:
        """Build Gemini planning contexts from planned results."""
        contexts: list[PlanningContext] = []

        for _, row in results.iterrows():
            contexts.append(
                PlanningContext(
                    resource_id=str(row["resource_id"]),
                    resource_type=str(row["resource_type"]),
                    environment=str(row.get("environment", "unknown")),
                    business_critical=bool(row.get("business_critical", False)),
                    attached_to_load_balancer=bool(
                        row.get("attached_to_load_balancer", False)
                    ),
                    member_of_autoscaling_group=bool(
                        row.get("member_of_autoscaling_group", False)
                    ),
                    owner_exists=bool(row.get("owner_exists", False)),
                    recent_activity_days=int(row.get("recent_activity_days", 999)),
                    waste_score=float(row["waste_score"]),
                    risk_score=int(row.get("risk_score", 0)),
                    risk_level=str(row["risk_level"]),
                    recommendation=str(row["recommendation"]),
                    risk_explanation=str(row.get("risk_explanation", "")),
                    monthly_cost=float(row["monthly_cost"]),
                    annual_cost=float(row["annual_cost"]),
                    potential_annual_savings=float(row["potential_annual_savings"]),
                    action=row["action"],
                    execution_steps=self._parse_execution_steps(row["execution_steps"]),
                )
            )

        return contexts

    def _apply_justifications(
        self,
        results: pd.DataFrame,
        justifications: list[PlanningJustification],
    ) -> pd.DataFrame:
        """Attach Gemini justifications to planned results."""
        enriched = results.copy()
        enriched["business_justification"] = [
            justification.business_justification for justification in justifications
        ]
        enriched["technical_justification"] = [
            justification.technical_justification for justification in justifications
        ]
        enriched["expected_outcome"] = [
            justification.expected_outcome for justification in justifications
        ]
        enriched["justification_source"] = [
            justification.source for justification in justifications
        ]
        return enriched

    def _build_approval_packages(self, results: pd.DataFrame) -> list[ApprovalPackage]:
        """Build human-reviewable approval packages for the dashboard."""
        packages: list[ApprovalPackage] = []

        for _, row in results.iterrows():
            packages.append(
                ApprovalPackage(
                    resource_id=str(row["resource_id"]),
                    action=row["action"],
                    risk_level=str(row["risk_level"]),
                    estimated_savings=float(row["estimated_savings"]),
                    business_justification=str(row["business_justification"]),
                    execution_steps=self._parse_execution_steps(row["execution_steps"]),
                )
            )

        return packages

    def run(self) -> pd.DataFrame:
        """Execute the full planner pipeline."""
        merged_data = self.load_inputs()
        planned = self._planner.plan_all(merged_data)

        contexts = self._build_planning_contexts(planned)
        justifications = self._gemini_planner.generate_batch(contexts)
        results = self._apply_justifications(planned, justifications)

        export_columns = [
            "resource_id",
            "action",
            "risk_level",
            "estimated_savings",
            "execution_steps",
            "business_justification",
        ]
        export_frame = results.copy()
        export_frame["execution_steps"] = export_frame["execution_steps"].apply(
            self._format_execution_steps
        )

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        export_frame[export_columns].to_csv(self._output_path, index=False)
        logger.info("Remediation plan saved to %s", self._output_path)

        approval_packages = self._build_approval_packages(results)
        self._approval_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._approval_path, "w", encoding="utf-8") as handle:
            json.dump(
                [package.to_dict() for package in approval_packages],
                handle,
                indent=2,
            )
        logger.info("Approval packages saved to %s", self._approval_path)

        figure_paths = self._visualizer.generate_all(results)
        summary = PlannerReporter.summarize(results)
        top_plans = PlannerReporter.get_top_plans(results)

        PlannerReporter.print_summary(summary)
        PlannerReporter.print_top_plans(top_plans)

        print("=== OUTPUT FILES ===\n")
        print(f"Remediation CSV : {self._output_path}")
        print(f"Approval JSON   : {self._approval_path}")
        for path in figure_paths:
            print(f"Figure          : {path}")
        print()

        return results


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """Run the Planner Agent pipeline."""
    _configure_logging()

    try:
        PlannerPipeline().run()
        return 0
    except PlannerDataError as exc:
        logger.error("Data error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Planner pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
