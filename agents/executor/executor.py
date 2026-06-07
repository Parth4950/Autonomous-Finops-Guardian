"""
Executor Agent — executes approved remediation plans against AWS.

Default mode is simulation — no live infrastructure changes are made until
EXECUTION_MODE=real is explicitly enabled in the environment.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.executor.execution_history import (
    ExecutionHistoryStore,
    ExecutionRecord,
    format_timestamp,
    utc_now,
)
from agents.executor.rollback_manager import RollbackManager, RollbackPlan
from workflow.approval_manager import ApprovalManager
from workflow.models import ApprovalRecord

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = MODULE_DIR / "results"
DEFAULT_FIGURES_DIR = MODULE_DIR / "figures"
DEFAULT_LOGS_DIR = MODULE_DIR / "logs"
DEFAULT_ROLLBACK_PATH = DEFAULT_RESULTS_DIR / "rollback_plans.json"
DEFAULT_APPROVALS_PATH = _PROJECT_ROOT / "workflow" / "results" / "approvals.json"

ExecutionMode = Literal["simulation", "real"]
ExecutableAction = Literal["terminate", "resize", "stop", "snapshot_and_delete"]

EXECUTABLE_ACTIONS: frozenset[str] = frozenset(
    {"terminate", "resize", "stop", "snapshot_and_delete"}
)

SIMULATION_LOG_TEMPLATES: dict[str, list[str]] = {
    "terminate": [
        "[INFO] Starting terminate workflow for {resource_id}",
        "[INFO] Creating backup snapshot for {resource_id}",
        "[INFO] Backup snapshot created: snap-sim-{suffix}",
        "[INFO] Validation complete — backup verified",
        "[INFO] Terminating instance {resource_id}",
        "[INFO] Resource terminated successfully",
    ],
    "resize": [
        "[INFO] Starting resize workflow for {resource_id}",
        "[INFO] Stopping instance {resource_id}",
        "[INFO] Instance stopped successfully",
        "[INFO] Modifying instance type for {resource_id}",
        "[INFO] Instance type modified to smaller size",
        "[INFO] Restarting instance {resource_id}",
        "[INFO] Instance restarted and validated",
    ],
    "stop": [
        "[INFO] Starting stop workflow for {resource_id}",
        "[INFO] Stopping instance {resource_id}",
        "[INFO] Instance stopped successfully",
        "[INFO] Validation complete — instance state is stopped",
        "[INFO] Resource owner notification queued",
    ],
    "snapshot_and_delete": [
        "[INFO] Starting snapshot_and_delete workflow for {resource_id}",
        "[INFO] Creating snapshot for volume {resource_id}",
        "[INFO] Snapshot created: snap-sim-{suffix}",
        "[INFO] Validation complete — snapshot verified",
        "[INFO] Deleting EBS volume {resource_id}",
        "[INFO] EBS volume deleted successfully",
    ],
}


class ExecutorDataError(FileNotFoundError):
    """Raised when required upstream approval data is missing."""


class ExecutionError(Exception):
    """Raised when remediation execution fails."""


class UnsupportedActionError(ExecutionError):
    """Raised when an action cannot be executed."""


@dataclass(frozen=True)
class ExecutionRequest:
    """Input payload for remediation execution."""

    approval_id: str
    resource_id: str
    action: str
    risk_level: str
    execution_steps: list[str]

    @classmethod
    def from_approval_record(cls, record: ApprovalRecord) -> ExecutionRequest:
        """Build an execution request from an approved workflow record."""
        return cls(
            approval_id=record.approval_id,
            resource_id=record.resource_id,
            action=record.action,
            risk_level=record.risk_level,
            execution_steps=list(record.execution_steps),
        )


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of a remediation execution attempt."""

    execution_id: str
    request: ExecutionRequest
    status: Literal["success", "failed"]
    mode: ExecutionMode
    log_path: Path
    rollback_plan: RollbackPlan
    error_message: str | None = None


@dataclass(frozen=True)
class ExecutionSummary:
    """Aggregate execution metrics."""

    total_executions: int
    successful: int
    failed: int
    rolled_back: int
    rollback_plans_generated: int
    mode: ExecutionMode


class AWSRemediationHooks:
    """
    Future AWS remediation hooks via Boto3.

    Methods are stubs only — real execution is disabled until
    EXECUTION_MODE=real is enabled and implementations are completed.
    """

    def __init__(self, region: str | None = None) -> None:
        self._region = region
        self._ec2_client: Any | None = None
        self._ebs_client: Any | None = None

    def _get_ec2_client(self) -> Any:
        """Return a Boto3 EC2 client (lazy-loaded)."""
        if self._ec2_client is None:
            from backend.utils.aws_client import AWSClientHelper

            self._ec2_client = AWSClientHelper(region=self._region).create_client("ec2")
        return self._ec2_client

    def _get_ebs_client(self) -> Any:
        """Return a Boto3 EC2 client for EBS operations (lazy-loaded)."""
        return self._get_ec2_client()

    def terminate_instance(self, instance_id: str) -> dict[str, Any]:
        """Terminate an EC2 instance. Stub — not implemented."""
        raise NotImplementedError(
            "Real terminate_instance execution is not enabled. "
            "Set EXECUTION_MODE=real after implementing safety controls."
        )

    def stop_instance(self, instance_id: str) -> dict[str, Any]:
        """Stop an EC2 instance. Stub — not implemented."""
        raise NotImplementedError(
            "Real stop_instance execution is not enabled. "
            "Set EXECUTION_MODE=real after implementing safety controls."
        )

    def create_snapshot(self, volume_id: str) -> dict[str, Any]:
        """Create an EBS snapshot. Stub — not implemented."""
        raise NotImplementedError(
            "Real create_snapshot execution is not enabled. "
            "Set EXECUTION_MODE=real after implementing safety controls."
        )

    def delete_volume(self, volume_id: str) -> dict[str, Any]:
        """Delete an EBS volume. Stub — not implemented."""
        raise NotImplementedError(
            "Real delete_volume execution is not enabled. "
            "Set EXECUTION_MODE=real after implementing safety controls."
        )

    def modify_instance_type(self, instance_id: str, instance_type: str) -> dict[str, Any]:
        """Modify an EC2 instance type. Stub — not implemented."""
        raise NotImplementedError(
            "Real modify_instance_type execution is not enabled. "
            "Set EXECUTION_MODE=real after implementing safety controls."
        )


class ExecutionLogger:
    """Write structured execution logs to disk."""

    def __init__(self, logs_dir: Path = DEFAULT_LOGS_DIR) -> None:
        self._logs_dir = logs_dir
        self._logs_dir.mkdir(parents=True, exist_ok=True)

    def write_log(
        self,
        execution_id: str,
        lines: list[str],
    ) -> Path:
        """Persist execution log lines and return the log file path."""
        log_path = self._logs_dir / f"execution_{execution_id}.log"
        content = "\n".join(lines) + "\n"
        log_path.write_text(content, encoding="utf-8")
        return log_path


class Executor:
    """
    Remediation execution engine for approved cloud optimization actions.

    Executes approved plans in simulation mode by default, with AWS hooks
    reserved for future real execution.
    """

    def __init__(
        self,
        mode: ExecutionMode | None = None,
        aws_hooks: AWSRemediationHooks | None = None,
        rollback_manager: RollbackManager | None = None,
        execution_logger: ExecutionLogger | None = None,
    ) -> None:
        load_dotenv(_PROJECT_ROOT / ".env", override=True)
        self._mode = mode or self._load_execution_mode()
        self._aws_hooks = aws_hooks or AWSRemediationHooks()
        self._rollback_manager = rollback_manager or RollbackManager()
        self._execution_logger = execution_logger or ExecutionLogger()
        logger.info("Executor initialized in %s mode", self._mode)

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @staticmethod
    def _load_execution_mode() -> ExecutionMode:
        """Load execution mode from environment with simulation as default."""
        raw_mode = os.getenv("EXECUTION_MODE", "simulation").strip().lower()
        if raw_mode not in {"simulation", "real"}:
            logger.warning(
                "Unknown EXECUTION_MODE '%s' — defaulting to simulation.",
                raw_mode,
            )
            return "simulation"
        return raw_mode  # type: ignore[return-value]

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute an approved remediation request.

        Args:
            request: Approved execution request from the workflow layer.

        Returns:
            ExecutionResult with status, logs, and rollback plan.

        Raises:
            UnsupportedActionError: When the action is not executable.
            ExecutionError: When execution fails.
        """
        if request.action not in EXECUTABLE_ACTIONS:
            raise UnsupportedActionError(
                f"Action '{request.action}' is not executable by the Executor."
            )

        execution_id = str(uuid.uuid4())
        rollback_plan = self._rollback_manager.generate_plan(
            approval_id=request.approval_id,
            resource_id=request.resource_id,
            action=request.action,
        )

        try:
            if self._mode == "simulation":
                log_lines = self._simulate_execution(request, execution_id)
            else:
                log_lines = self._execute_real(request, execution_id)

            log_path = self._execution_logger.write_log(execution_id, log_lines)
            logger.info(
                "Execution %s completed successfully for %s (%s)",
                execution_id,
                request.resource_id,
                request.action,
            )
            return ExecutionResult(
                execution_id=execution_id,
                request=request,
                status="success",
                mode=self._mode,
                log_path=log_path,
                rollback_plan=rollback_plan,
            )
        except Exception as exc:
            log_lines = [
                f"[ERROR] Execution failed for {request.resource_id}",
                f"[ERROR] {type(exc).__name__}: {exc}",
            ]
            log_path = self._execution_logger.write_log(execution_id, log_lines)
            logger.error(
                "Execution %s failed for %s: %s",
                execution_id,
                request.resource_id,
                exc,
            )
            return ExecutionResult(
                execution_id=execution_id,
                request=request,
                status="failed",
                mode=self._mode,
                log_path=log_path,
                rollback_plan=rollback_plan,
                error_message=str(exc),
            )

    def _simulate_execution(
        self,
        request: ExecutionRequest,
        execution_id: str,
    ) -> list[str]:
        """Simulate remediation execution and return log lines."""
        suffix = execution_id[:8]
        template = SIMULATION_LOG_TEMPLATES.get(request.action, [])
        log_lines = [
            f"[INFO] Execution ID: {execution_id}",
            f"[INFO] Mode: simulation",
            f"[INFO] Approval ID: {request.approval_id}",
            f"[INFO] Risk Level: {request.risk_level}",
            f"[INFO] Planned Steps: {' -> '.join(request.execution_steps)}",
        ]

        for line in template:
            log_lines.append(
                line.format(resource_id=request.resource_id, suffix=suffix)
            )

        log_lines.append("[INFO] Rollback plan prepared and stored")
        log_lines.append("[INFO] Simulation complete — no AWS resources modified")
        return log_lines

    def _execute_real(
        self,
        request: ExecutionRequest,
        execution_id: str,
    ) -> list[str]:
        """
        Execute remediation against AWS using Boto3 hooks.

        Real execution is intentionally gated behind stub implementations.
        """
        log_lines = [
            f"[INFO] Execution ID: {execution_id}",
            f"[INFO] Mode: real",
            f"[INFO] Approval ID: {request.approval_id}",
        ]

        if request.action == "terminate":
            self._aws_hooks.terminate_instance(request.resource_id)
        elif request.action == "stop":
            self._aws_hooks.stop_instance(request.resource_id)
        elif request.action == "snapshot_and_delete":
            self._aws_hooks.create_snapshot(request.resource_id)
            self._aws_hooks.delete_volume(request.resource_id)
        elif request.action == "resize":
            self._aws_hooks.modify_instance_type(request.resource_id, "t3.micro")

        log_lines.append("[INFO] Real execution path invoked")
        return log_lines


class ExecutorReporter:
    """Format and print execution summaries."""

    @staticmethod
    def summarize(records: list[ExecutionRecord], rollback_count: int, mode: ExecutionMode) -> ExecutionSummary:
        """Compute aggregate execution metrics."""
        return ExecutionSummary(
            total_executions=len(records),
            successful=sum(record.status == "success" for record in records),
            failed=sum(record.status == "failed" for record in records),
            rolled_back=sum(record.status == "rolled_back" for record in records),
            rollback_plans_generated=rollback_count,
            mode=mode,
        )

    @staticmethod
    def print_summary(summary: ExecutionSummary, recent: pd.DataFrame) -> None:
        """Print execution summary to stdout."""
        print("\n=== EXECUTION SUMMARY ===\n")
        print(f"Execution Mode            : {summary.mode}")
        print(f"Total Executions          : {summary.total_executions}")
        print(f"Successful Actions        : {summary.successful}")
        print(f"Failed Actions            : {summary.failed}")
        print(f"Rolled Back Actions       : {summary.rolled_back}")
        print(f"Rollback Plans Generated  : {summary.rollback_plans_generated}")
        print()
        print("=== RECENT EXECUTIONS ===\n")
        if recent.empty:
            print("No executions recorded.")
        else:
            print(recent.to_string(index=False))
        print()


class ExecutorVisualizer:
    """Generate execution analytics visualizations."""

    def __init__(self, figures_dir: Path = DEFAULT_FIGURES_DIR) -> None:
        self._figures_dir = figures_dir

    def generate_all(self, records: list[ExecutionRecord]) -> list[Path]:
        """Create and save all execution visualizations."""
        self._figures_dir.mkdir(parents=True, exist_ok=True)

        if not records:
            logger.warning("No execution records available for visualization.")
            return []

        dataframe = pd.DataFrame([record.to_csv_row() for record in records])
        saved = [
            self._plot_status_distribution(dataframe),
            self._plot_action_distribution(dataframe),
            self._plot_execution_timeline(dataframe),
        ]
        logger.info("Saved %d figure(s) to %s", len(saved), self._figures_dir)
        return saved

    def _plot_status_distribution(self, dataframe: pd.DataFrame) -> Path:
        """Plot execution outcome distribution."""
        output_path = self._figures_dir / "execution_status_distribution.png"
        order = ["success", "failed", "rolled_back"]
        counts = dataframe["status"].value_counts().reindex(order, fill_value=0)
        colors = {"success": "#27ae60", "failed": "#c0392b", "rolled_back": "#f39c12"}

        fig, ax = plt.subplots(figsize=(8, 5))
        bars = ax.bar(
            order,
            [counts[status] for status in order],
            color=[colors[status] for status in order],
            edgecolor="white",
        )
        ax.set_title("Execution Status Distribution")
        ax.set_ylabel("Count")

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.05,
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

    def _plot_action_distribution(self, dataframe: pd.DataFrame) -> Path:
        """Plot executed action type distribution."""
        output_path = self._figures_dir / "action_type_distribution.png"
        counts = dataframe["action"].value_counts()

        fig, ax = plt.subplots(figsize=(9, 5))
        bars = ax.bar(counts.index, counts.values, color="#3498db", edgecolor="white")
        ax.set_title("Action Type Distribution")
        ax.set_ylabel("Count")
        ax.tick_params(axis="x", rotation=20)

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.05,
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

    def _plot_execution_timeline(self, dataframe: pd.DataFrame) -> Path:
        """Plot execution events over time."""
        output_path = self._figures_dir / "execution_timeline.png"
        timeline = dataframe.copy()
        timeline["timestamp"] = pd.to_datetime(timeline["timestamp"])
        timeline = timeline.sort_values("timestamp")

        color_map = {"success": "#27ae60", "failed": "#c0392b", "rolled_back": "#f39c12"}
        colors = [color_map.get(status, "#34495e") for status in timeline["status"]]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.scatter(
            timeline["timestamp"],
            range(len(timeline)),
            c=colors,
            s=80,
            edgecolors="white",
        )
        ax.set_title("Execution Timeline")
        ax.set_xlabel("Timestamp (UTC)")
        ax.set_ylabel("Execution Sequence")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path


class ExecutorPipeline:
    """End-to-end Executor Agent workflow."""

    def __init__(
        self,
        approvals_path: Path = DEFAULT_APPROVALS_PATH,
        history_store: ExecutionHistoryStore | None = None,
        approval_manager: ApprovalManager | None = None,
        executor: Executor | None = None,
        visualizer: ExecutorVisualizer | None = None,
        rollback_path: Path = DEFAULT_ROLLBACK_PATH,
    ) -> None:
        self._approvals_path = approvals_path
        self._history_store = history_store or ExecutionHistoryStore(DEFAULT_RESULTS_DIR)
        self._approval_manager = approval_manager or ApprovalManager()
        self._executor = executor or Executor()
        self._visualizer = visualizer or ExecutorVisualizer()
        self._rollback_path = rollback_path

    def load_approved_requests(self) -> list[ExecutionRequest]:
        """Load approved, executable remediation requests from the workflow."""
        if not self._approvals_path.exists():
            raise ExecutorDataError(
                f"Approval records not found at {self._approvals_path}. "
                "Run workflow/approval_manager.py first."
            )

        approved = self._approval_manager.list_approved()
        requests: list[ExecutionRequest] = []

        for record in approved:
            if record.action not in EXECUTABLE_ACTIONS:
                logger.info(
                    "Skipping non-executable approved action '%s' for %s",
                    record.action,
                    record.resource_id,
                )
                continue

            if self._history_store.get_by_approval_id(record.approval_id):
                logger.info(
                    "Skipping already executed approval %s",
                    record.approval_id,
                )
                continue

            requests.append(ExecutionRequest.from_approval_record(record))

        logger.info("Loaded %d approved executable request(s)", len(requests))
        return requests

    def run(self) -> list[ExecutionRecord]:
        """Execute all approved remediation requests."""
        requests = self.load_approved_requests()
        results: list[ExecutionResult] = []
        rollback_plans: list[RollbackPlan] = []

        for request in requests:
            result = self._executor.execute(request)
            results.append(result)
            rollback_plans.append(result.rollback_plan)

            history_record = ExecutionRecord(
                execution_id=result.execution_id,
                approval_id=result.request.approval_id,
                resource_id=result.request.resource_id,
                action=result.request.action,
                status=result.status,
                timestamp=utc_now(),
                mode=result.mode,
                log_path=str(result.log_path),
                error_message=result.error_message,
            )
            self._history_store.append_record(history_record)

            if result.status == "success":
                self._approval_manager.mark_executed(
                    result.request.approval_id,
                    notes=f"Executed in {result.mode} mode.",
                )

        self._save_rollback_plans(rollback_plans)

        all_records = self._history_store.load_records()
        summary = ExecutorReporter.summarize(
            records=all_records,
            rollback_count=len(rollback_plans),
            mode=self._executor.mode,
        )
        recent = pd.DataFrame([record.to_csv_row() for record in all_records[-10:]])
        ExecutorReporter.print_summary(summary, recent)

        figure_paths = self._visualizer.generate_all(all_records)

        print("=== OUTPUT FILES ===\n")
        print(f"Execution CSV : {self._history_store.csv_path}")
        print(f"Rollback JSON : {self._rollback_path}")
        for result in results:
            print(f"Execution Log : {result.log_path}")
        for path in figure_paths:
            print(f"Figure        : {path}")
        print()

        return all_records

    def _save_rollback_plans(self, plans: list[RollbackPlan]) -> None:
        """Persist rollback plans generated during execution."""
        self._rollback_path.parent.mkdir(parents=True, exist_ok=True)

        existing: list[dict[str, Any]] = []
        if self._rollback_path.exists():
            with open(self._rollback_path, encoding="utf-8") as handle:
                payload = json.load(handle)
                if isinstance(payload, list):
                    existing = payload

        existing.extend(plan.to_dict() for plan in plans)
        with open(self._rollback_path, "w", encoding="utf-8") as handle:
            json.dump(existing, handle, indent=2)

        logger.info("Saved %d rollback plan(s) to %s", len(plans), self._rollback_path)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """Run the Executor Agent pipeline."""
    _configure_logging()

    try:
        ExecutorPipeline().run()
        return 0
    except ExecutorDataError as exc:
        logger.error("Data error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Executor pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
