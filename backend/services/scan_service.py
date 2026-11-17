"""Orchestrates isolated, user-owned FinOps pipeline scans."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.config.settings import CredentialsEncryptionError
from backend.db.session import get_session_factory
from backend.models.auth import User
from backend.models.finops import AWSAccount, Scan, ScanStage
from backend.models.paths import PROJECT_ROOT, scan_workspace_path
from backend.utils.aws_client import sanitize_aws_error_message
from backend.utils.credential_encryption import CredentialTamperError

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
    discovery = (
        ("Discovering AWS resources", AWS_DISCOVERY_SCRIPT)
        if mode == "aws"
        else ("Discovering cloud resources", SYNTHETIC_DISCOVERY_SCRIPT)
    )
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
    aws_account_id: int | None = None
    region: str | None = None
    steps: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class _ScanAWSContext:
    """In-memory AWS credential and identity bundle for one user-owned scan."""

    access_key_id: str
    secret_access_key: str
    session_token: str | None
    region: str
    aws_account_id: str | None
    connection_id: int | None = None

    def __repr__(self) -> str:
        return (
            f"_ScanAWSContext(connection_id={self.connection_id}, "
            f"aws_account_id={self.aws_account_id!r}, region={self.region!r})"
        )


class ScanInProgressError(RuntimeError):
    """Raised when this user already has a running scan."""


class ScanConfigurationError(ValueError):
    """Raised when scan prerequisites are missing (e.g. AWS credentials)."""


class ScanService:
    """Run the existing pipeline with a separate file workspace per scan."""

    def __init__(
        self,
        project_root: Path = PROJECT_ROOT,
        session_factory: sessionmaker[Session] | None = None,
        process_runner: Callable = subprocess.run,
    ) -> None:
        self._project_root = project_root
        self._session_factory = session_factory or get_session_factory()
        self._runner = process_runner
        self._lock = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}

    def start_scan(
        self,
        user_id: int,
        mode: ScanMode = "synthetic",
        aws_account_id: int | None = None,
        region: str | None = None,
    ) -> ScanState:
        pipeline_steps = build_pipeline_steps(mode)
        aws_context: _ScanAWSContext | None = None

        with self._lock:
            with self._session_factory() as db:
                active = db.scalar(
                    select(Scan.scan_id).where(
                        Scan.user_id == user_id,
                        Scan.status.in_(("pending", "running")),
                    ).limit(1)
                )
                if active:
                    raise ScanInProgressError("A cloud scan is already in progress.")
                if db.get(User, user_id) is None:
                    raise ValueError("Scan owner does not exist")

                if mode == "aws":
                    aws_context = self._resolve_aws_context(
                        db,
                        user_id=user_id,
                        aws_account_id=aws_account_id,
                        region=region,
                    )

                scan_id = str(uuid.uuid4())
                workspace = scan_workspace_path(user_id, scan_id)
                workspace.mkdir(parents=True, exist_ok=False)
                db.add(Scan(
                    scan_id=scan_id, user_id=user_id, mode=mode, status="running", progress=0,
                    message=f"Scan started ({mode} mode)", started_at=datetime.now(timezone.utc),
                ))
                db.add_all([
                    ScanStage(user_id=user_id, scan_id=scan_id, stage_order=order, name=name, status="pending")
                    for order, (name, _) in enumerate(pipeline_steps, start=1)
                ])
                db.commit()

            thread = threading.Thread(
                target=self._run_pipeline,
                args=(scan_id, user_id, mode, pipeline_steps, workspace, aws_context),
                daemon=True,
                name=f"cloud-scan-{scan_id[:8]}",
            )
            self._threads[scan_id] = thread
            thread.start()
            state = self._read_state(scan_id, user_id)
            if aws_context is not None:
                state.aws_account_id = aws_context.connection_id
                state.region = aws_context.region
            return state

    def get_status(self, user_id: int) -> ScanState | None:
        with self._session_factory() as db:
            row = db.scalar(
                select(Scan).where(Scan.user_id == user_id).order_by(Scan.created_at.desc()).limit(1)
            )
            return self._state_from_row(db, row) if row else None

    def _read_state(self, scan_id: str, user_id: int) -> ScanState:
        with self._session_factory() as db:
            row = db.get(Scan, scan_id)
            if row is None or row.user_id != user_id:
                raise LookupError("Scan not found")
            return self._state_from_row(db, row)

    @staticmethod
    def _state_from_row(db: Session, row: Scan) -> ScanState:
        stages = db.scalars(
            select(ScanStage).where(ScanStage.scan_id == row.scan_id).order_by(ScanStage.stage_order)
        ).all()
        return ScanState(
            scan_id=row.scan_id, status=row.status, progress=row.progress,
            current_step=row.current_stage, message=row.message, error=row.error_message,
            scan_mode=row.mode, steps=[{"name": stage.name, "status": stage.status} for stage in stages],
        )

    def _resolve_aws_context(
        self,
        db: Session,
        *,
        user_id: int,
        aws_account_id: int | None,
        region: str | None,
    ) -> _ScanAWSContext:
        from backend.config import aws_scan_enabled
        from backend.services.aws_account_service import _validate_region
        from backend.utils.aws_client import AWSConfigurationError, get_aws_credentials

        if not aws_scan_enabled():
            raise ScanConfigurationError(
                "Live AWS scan is disabled on this deployment. Use synthetic mode for hosted demos, "
                "or run locally with AWS credentials."
            )

        cleaned_region: str | None = None
        if region is not None and region.strip():
            try:
                cleaned_region = _validate_region(region)
            except ValueError as exc:
                raise ScanConfigurationError(str(exc)) from exc

        account: AWSAccount | None = None
        if aws_account_id is not None:
            account = db.scalar(
                select(AWSAccount).where(
                    AWSAccount.id == aws_account_id,
                    AWSAccount.user_id == user_id,
                )
            )
            if account is None:
                raise LookupError("AWS account not found.")
        else:
            account = db.scalar(
                select(AWSAccount)
                .where(AWSAccount.user_id == user_id)
                .order_by(AWSAccount.created_at.desc(), AWSAccount.id.desc())
                .limit(1)
            )

        if account is not None:
            try:
                decrypted = account.decrypt_credentials(requesting_user_id=user_id)
            except (CredentialTamperError, CredentialsEncryptionError) as exc:
                raise ScanConfigurationError(
                    "Stored AWS account credentials could not be decrypted. Please reconnect your AWS account."
                ) from exc
            resolved_region = cleaned_region or account.default_region or "ap-south-1"
            return _ScanAWSContext(
                access_key_id=decrypted.access_key_id,
                secret_access_key=decrypted.secret_access_key,
                session_token=decrypted.session_token,
                region=resolved_region,
                aws_account_id=account.aws_account_id,
                connection_id=account.id,
            )

        try:
            env_creds = get_aws_credentials(region=cleaned_region)
        except (AWSConfigurationError, FileNotFoundError) as exc:
            raise ScanConfigurationError(
                "AWS credentials are required for live scans. Connect an AWS account or configure credentials in .env."
            ) from exc

        return _ScanAWSContext(
            access_key_id=env_creds.access_key_id,
            secret_access_key=env_creds.secret_access_key,
            session_token=env_creds.session_token,
            region=env_creds.region,
            aws_account_id=None,
            connection_id=None,
        )

    def _run_pipeline(
        self,
        scan_id: str,
        user_id: int,
        mode: ScanMode,
        pipeline_steps: list[tuple[str, str | None]],
        workspace: Path,
        aws_context: _ScanAWSContext | None = None,
    ) -> None:
        total = len(pipeline_steps)
        env = os.environ.copy()
        env["FINOPS_SCAN_MODE"] = mode
        env["FINOPS_WORKSPACE_DIR"] = str(workspace)
        if mode == "aws" and aws_context is not None:
            env["FINOPS_AWS_CREDENTIAL_SOURCE"] = "account"
            env["AWS_ACCESS_KEY_ID"] = aws_context.access_key_id
            env["AWS_SECRET_ACCESS_KEY"] = aws_context.secret_access_key
            env["AWS_REGION"] = aws_context.region
            if aws_context.session_token:
                env["AWS_SESSION_TOKEN"] = aws_context.session_token
            else:
                env.pop("AWS_SESSION_TOKEN", None)
            if aws_context.aws_account_id:
                env["FINOPS_AWS_ACCOUNT_ID"] = aws_context.aws_account_id
        else:
            # Never leak parent-process AWS credentials into synthetic scan subprocesses
            env.pop("FINOPS_AWS_CREDENTIAL_SOURCE", None)
            env.pop("FINOPS_AWS_ACCOUNT_ID", None)

        project_root_str = str(self._project_root)
        existing_pythonpath = env.get("PYTHONPATH", "")
        if project_root_str not in existing_pythonpath.split(os.pathsep):
            env["PYTHONPATH"] = f"{project_root_str}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else project_root_str

        try:
            for index, (step_name, script_rel) in enumerate(pipeline_steps):
                self._update_step(scan_id, user_id, index, step_name, "running", total)
                try:
                    if script_rel is None:
                        self._run_in_process_step(step_name, self._project_root, workspace)
                    else:
                        script_path = self._project_root / script_rel
                        if not script_path.exists():
                            raise FileNotFoundError(f"Pipeline script not found: {script_rel}")
                        logger.info("Cloud scan %s — running %s", scan_id[:8], script_rel)
                        result = self._runner(
                            [PYTHON, str(script_path)], cwd=self._project_root, capture_output=True,
                            text=True, check=False, env=env,
                        )
                        if result.returncode != 0:
                            detail = (result.stderr or result.stdout or "Unknown error").strip()
                            last_line = detail.splitlines()[-1] if detail else "Process exited with error"
                            raise RuntimeError(sanitize_aws_error_message(last_line))
                except Exception as exc:
                    safe_detail = sanitize_aws_error_message(exc)
                    logger.error("Cloud scan %s failed during stage %s: %s", scan_id[:8], step_name, safe_detail)
                    self._fail_scan(scan_id, user_id, f"{step_name} failed: {safe_detail}", index)
                    return
                progress = int(((index + 1) / total) * 100)
                self._update_step(scan_id, user_id, index, step_name, "completed", total, progress)
            try:
                if mode == "aws" and aws_context is not None:
                    self._enrich_aws_scan_source(workspace, aws_context)
                from backend.services.scan_output_persistence import persist_scan_outputs

                with self._session_factory() as db:
                    persist_scan_outputs(db, user_id=user_id, scan_id=scan_id, workspace=workspace)
                    db.commit()
            except Exception as exc:
                safe_detail = sanitize_aws_error_message(exc)
                logger.error("Cloud scan %s output persistence failed: %s", scan_id[:8], safe_detail)
                self._fail_scan(scan_id, user_id, f"Persisting scan results failed: {safe_detail}", None)
                return
            self._finish_scan(scan_id, user_id, "completed", 100, f"Scan completed successfully ({mode} mode)")
            logger.info("Cloud scan %s completed (%s mode)", scan_id[:8], mode)
        finally:
            self._threads.pop(scan_id, None)

    @staticmethod
    def _enrich_aws_scan_source(workspace: Path, aws_context: _ScanAWSContext) -> None:
        """Ensure scan_source.json records the verified AWS account_id and region without secrets."""
        source_path = workspace / "synthetic_data" / "scan_source.json"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {}
        if source_path.is_file():
            try:
                loaded = json.loads(source_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = loaded
            except json.JSONDecodeError:
                payload = {}
        payload["mode"] = "aws"
        payload["region"] = aws_context.region
        if aws_context.aws_account_id:
            payload["account_id"] = aws_context.aws_account_id
        elif "account_id" not in payload:
            payload["account_id"] = "aws"
        if aws_context.connection_id is not None:
            payload["aws_connection_id"] = aws_context.connection_id
        source_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _run_in_process_step(step_name: str, project_root: Path, workspace: Path) -> None:
        if step_name != "Ingesting approval queue":
            raise ValueError(f"Unknown in-process pipeline step: {step_name}")
        import pandas as pd
        from workflow.approval_manager import ApprovalManager
        from workflow.approval_queue import ApprovalQueue

        resources_csv = workspace / "synthetic_data" / "cloud_resources.csv"
        packages = workspace / "agents" / "planner" / "results" / "approval_packages.json"
        active_resource_ids: set[str] = set()
        if resources_csv.exists():
            inventory = pd.read_csv(resources_csv)
            if "resource_id" in inventory.columns:
                active_resource_ids = {str(value) for value in inventory["resource_id"].tolist()}
        queue = ApprovalQueue(workspace / "workflow" / "results", workspace / "workflow" / "history")
        manager = ApprovalManager(queue=queue)
        if active_resource_ids:
            manager.supersede_stale_pending(active_resource_ids)
        created = manager.ingest_planner_packages(packages_path=packages)
        logger.info("Ingested %d approval request(s); active inventory=%d resource(s)", len(created), len(active_resource_ids))

    def _update_step(self, scan_id: str, user_id: int, index: int, name: str, state: str, total: int, progress: int | None = None) -> None:
        with self._session_factory() as db:
            scan = db.get(Scan, scan_id)
            stage = db.scalar(select(ScanStage).where(ScanStage.scan_id == scan_id, ScanStage.stage_order == index + 1))
            if scan is None or scan.user_id != user_id or stage is None:
                return
            now = datetime.now(timezone.utc)
            scan.current_stage = name
            scan.progress = progress if progress is not None else int((index / total) * 100)
            scan.updated_at = now
            if state == "running":
                stage.started_at = now
            else:
                stage.completed_at = now
            stage.status = state
            db.commit()

    def _finish_scan(self, scan_id: str, user_id: int, status: str, progress: int, message: str, error: str | None = None) -> None:
        with self._session_factory() as db:
            scan = db.get(Scan, scan_id)
            if scan is None or scan.user_id != user_id:
                return
            scan.status = status
            scan.progress = progress
            scan.current_stage = None
            scan.message = message
            scan.error_message = error
            scan.completed_at = datetime.now(timezone.utc)
            scan.updated_at = scan.completed_at
            db.commit()

    def _fail_scan(self, scan_id: str, user_id: int, error: str, index: int | None) -> None:
        logger.error("Cloud scan %s failed: %s", scan_id[:8], error)
        with self._session_factory() as db:
            scan = db.get(Scan, scan_id)
            stage = db.scalar(select(ScanStage).where(ScanStage.scan_id == scan_id, ScanStage.stage_order == index + 1)) if index is not None else None
            if scan is None or scan.user_id != user_id:
                return
            if stage is not None:
                stage.status = "failed"
                stage.error_message = error
                stage.completed_at = datetime.now(timezone.utc)
            scan.status = "failed"
            scan.error_message = error
            scan.message = "Scan failed"
            scan.current_stage = None
            scan.completed_at = datetime.now(timezone.utc)
            scan.updated_at = scan.completed_at
            db.commit()
