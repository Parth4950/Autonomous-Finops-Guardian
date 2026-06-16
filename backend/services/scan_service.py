"""Orchestrates FinOps pipeline scans triggered from the dashboard."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from backend.models.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

PYTHON = sys.executable
ScanMode = Literal["synthetic", "aws"]

SYNTHETIC_DISCOVERY_SCRIPT = "synthetic_data/generate_resources.py"
AWS_DISCOVERY_SCRIPT = "agents/scout/export_resources.py"

SHARED_PIPELINE_TAIL: list[tuple[str, str | None]] = [
    ("Detecting waste anomalies", "ml/isolation_forest/isolation_detector.py"),
    ("Forecasting utilization", "ml/forecasting/prophet_forecaster.py"),
    ("Exporting forecast dashboard", "ml/forecasting/export_forecast_json.py"),
    ("Assessing operational risk", "agents/risk_assessor/risk_assessor.py"),
    ("Auditing financial waste", "agents/auditor/auditor.py"),
    ("Generating remediation plans", "agents/planner/planner.py"),
    ("Ingesting approval queue", None),
]


def build_pipeline_steps(mode: ScanMode) -> list[tuple[str, str | None]]:
    """Return scan pipeline steps for the selected discovery mode."""
    if mode == "aws":
        discovery = ("Discovering AWS resources", AWS_DISCOVERY_SCRIPT)
    else:
        discovery = ("Discovering cloud resources", SYNTHETIC_DISCOVERY_SCRIPT)
    return [discovery, *SHARED_PIPELINE_TAIL]


@dataclass
class ScanState:
    scan_id: str
    status: str = "running"
    progress: int = 0
    current_step: str | None = None
    message: str | None = None
    error: str | None = None
    scan_mode: ScanMode = "synthetic"
    steps: list[dict[str, str]] = field(default_factory=list)


class ScanInProgressError(RuntimeError):
    """Raised when a scan is already running."""


class ScanConfigurationError(ValueError):
    """Raised when scan prerequisites are missing (e.g. AWS credentials)."""


class ScanService:
    """Run the FinOps analysis pipeline and expose scan progress."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self._project_root = project_root
        self._lock = threading.Lock()
        self._state: ScanState | None = None
        self._thread: threading.Thread | None = None

    def start_scan(self, mode: ScanMode = "synthetic") -> ScanState:
        """Start a background cloud scan if none is running."""
        if mode == "aws":
            self._validate_aws_configuration()

        pipeline_steps = build_pipeline_steps(mode)

        with self._lock:
            if self._state and self._state.status == "running":
                raise ScanInProgressError("A cloud scan is already in progress.")

            scan_id = str(uuid.uuid4())
            self._state = ScanState(
                scan_id=scan_id,
                status="running",
                progress=0,
                scan_mode=mode,
                message=f"Scan started ({mode} mode)",
                steps=[{"name": name, "status": "pending"} for name, _ in pipeline_steps],
            )
            self._thread = threading.Thread(
                target=self._run_pipeline,
                args=(scan_id, mode, pipeline_steps),
                daemon=True,
                name=f"cloud-scan-{scan_id[:8]}",
            )
            self._thread.start()
            return self._state

    def get_status(self) -> ScanState | None:
        """Return the latest scan state."""
        with self._lock:
            return self._state

    def _validate_aws_configuration(self) -> None:
        from backend.config import aws_scan_enabled
        from backend.utils.aws_client import AWSConfigurationError, get_aws_credentials

        if not aws_scan_enabled():
            raise ScanConfigurationError(
                "Live AWS scan is disabled on this deployment. "
                "Use synthetic mode for hosted demos, or run locally with AWS credentials."
            )

        try:
            get_aws_credentials()
        except (AWSConfigurationError, FileNotFoundError) as exc:
            raise ScanConfigurationError(
                "AWS credentials are required for live scans. "
                "Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION in .env."
            ) from exc

    def _run_pipeline(
        self,
        scan_id: str,
        mode: ScanMode,
        pipeline_steps: list[tuple[str, str | None]],
    ) -> None:
        total = len(pipeline_steps)
        env = os.environ.copy()
        env["FINOPS_SCAN_MODE"] = mode
        project_root_str = str(self._project_root)
        existing_pythonpath = env.get("PYTHONPATH", "")
        if project_root_str not in existing_pythonpath.split(os.pathsep):
            env["PYTHONPATH"] = (
                f"{project_root_str}{os.pathsep}{existing_pythonpath}"
                if existing_pythonpath
                else project_root_str
            )

        for index, (step_name, script_rel) in enumerate(pipeline_steps):
            self._update_step(scan_id, index, step_name, "running", total)

            if script_rel is None:
                logger.info("Cloud scan %s — running in-process step: %s", scan_id[:8], step_name)
                try:
                    self._run_in_process_step(step_name, self._project_root)
                except Exception as exc:
                    self._fail_scan(scan_id, f"{step_name} failed: {exc}")
                    return
            else:
                script_path = self._project_root / script_rel

                if not script_path.exists():
                    self._fail_scan(scan_id, f"Pipeline script not found: {script_rel}")
                    return

                logger.info("Cloud scan %s — running %s", scan_id[:8], script_rel)
                try:
                    result = subprocess.run(
                        [PYTHON, str(script_path)],
                        cwd=self._project_root,
                        capture_output=True,
                        text=True,
                        check=False,
                        env=env,
                    )
                except OSError as exc:
                    self._fail_scan(scan_id, f"{step_name} failed: {exc}")
                    return

                if result.returncode != 0:
                    detail = (result.stderr or result.stdout or "Unknown error").strip()
                    tail = detail.splitlines()[-1] if detail else "Process exited with error"
                    self._fail_scan(scan_id, f"{step_name} failed: {tail}")
                    return

            completed_progress = int(((index + 1) / total) * 100)
            self._update_step(scan_id, index, step_name, "completed", total, completed_progress)

        with self._lock:
            if self._state and self._state.scan_id == scan_id:
                self._state.status = "completed"
                self._state.progress = 100
                self._state.current_step = None
                self._state.message = f"Scan completed successfully ({mode} mode)"
        logger.info("Cloud scan %s completed (%s mode)", scan_id[:8], mode)

    @staticmethod
    def _run_in_process_step(step_name: str, project_root: Path) -> None:
        """Run pipeline steps that execute in-process instead of via subprocess."""
        if step_name == "Ingesting approval queue":
            import pandas as pd

            from workflow.approval_manager import ApprovalManager

            resources_csv = project_root / "synthetic_data" / "cloud_resources.csv"
            active_resource_ids: set[str] = set()
            if resources_csv.exists():
                inventory = pd.read_csv(resources_csv)
                if "resource_id" in inventory.columns:
                    active_resource_ids = {
                        str(resource_id) for resource_id in inventory["resource_id"].tolist()
                    }

            manager = ApprovalManager()
            if active_resource_ids:
                manager.supersede_stale_pending(active_resource_ids)
            created = manager.ingest_planner_packages()
            logger.info(
                "Ingested %d approval request(s); active inventory=%d resource(s)",
                len(created),
                len(active_resource_ids),
            )
            return

        raise ValueError(f"Unknown in-process pipeline step: {step_name}")

    def _update_step(
        self,
        scan_id: str,
        index: int,
        step_name: str,
        step_status: str,
        total_steps: int,
        progress: int | None = None,
    ) -> None:
        with self._lock:
            if not self._state or self._state.scan_id != scan_id:
                return
            self._state.current_step = step_name
            self._state.steps[index]["status"] = step_status
            if progress is not None:
                self._state.progress = progress
            elif step_status == "running":
                self._state.progress = int((index / total_steps) * 100)

    def _fail_scan(self, scan_id: str, error: str) -> None:
        logger.error("Cloud scan %s failed: %s", scan_id[:8], error)
        with self._lock:
            if not self._state or self._state.scan_id != scan_id:
                return
            self._state.status = "failed"
            self._state.error = error
            self._state.message = "Scan failed"
            if self._state.current_step:
                for step in self._state.steps:
                    if step["name"] == self._state.current_step:
                        step["status"] = "failed"
                        break
