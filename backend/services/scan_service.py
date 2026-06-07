"""Orchestrates FinOps pipeline scans triggered from the dashboard."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from backend.models.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

PYTHON = sys.executable

PIPELINE_STEPS: list[tuple[str, str]] = [
    ("Discovering cloud resources", "synthetic_data/generate_resources.py"),
    ("Detecting waste anomalies", "ml/isolation_forest/isolation_detector.py"),
    ("Forecasting utilization", "ml/forecasting/prophet_forecaster.py"),
    ("Exporting forecast dashboard", "ml/forecasting/export_forecast_json.py"),
    ("Assessing operational risk", "agents/risk_assessor/risk_assessor.py"),
    ("Auditing financial waste", "agents/auditor/auditor.py"),
    ("Generating remediation plans", "agents/planner/planner.py"),
]


@dataclass
class ScanState:
    scan_id: str
    status: str = "running"
    progress: int = 0
    current_step: str | None = None
    message: str | None = None
    error: str | None = None
    steps: list[dict[str, str]] = field(default_factory=list)


class ScanInProgressError(RuntimeError):
    """Raised when a scan is already running."""


class ScanService:
    """Run the FinOps analysis pipeline and expose scan progress."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self._project_root = project_root
        self._lock = threading.Lock()
        self._state: ScanState | None = None
        self._thread: threading.Thread | None = None

    def start_scan(self) -> ScanState:
        """Start a background cloud scan if none is running."""
        with self._lock:
            if self._state and self._state.status == "running":
                raise ScanInProgressError("A cloud scan is already in progress.")

            scan_id = str(uuid.uuid4())
            self._state = ScanState(
                scan_id=scan_id,
                status="running",
                progress=0,
                message="Scan started",
                steps=[{"name": name, "status": "pending"} for name, _ in PIPELINE_STEPS],
            )
            self._thread = threading.Thread(
                target=self._run_pipeline,
                args=(scan_id,),
                daemon=True,
                name=f"cloud-scan-{scan_id[:8]}",
            )
            self._thread.start()
            return self._state

    def get_status(self) -> ScanState | None:
        """Return the latest scan state."""
        with self._lock:
            return self._state

    def _run_pipeline(self, scan_id: str) -> None:
        total = len(PIPELINE_STEPS)

        for index, (step_name, script_rel) in enumerate(PIPELINE_STEPS):
            self._update_step(scan_id, index, step_name, "running")
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
            self._update_step(scan_id, index, step_name, "completed", completed_progress)

        with self._lock:
            if self._state and self._state.scan_id == scan_id:
                self._state.status = "completed"
                self._state.progress = 100
                self._state.current_step = None
                self._state.message = "Scan completed successfully"
        logger.info("Cloud scan %s completed", scan_id[:8])

    def _update_step(
        self,
        scan_id: str,
        index: int,
        step_name: str,
        step_status: str,
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
                self._state.progress = int((index / len(PIPELINE_STEPS)) * 100)

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
