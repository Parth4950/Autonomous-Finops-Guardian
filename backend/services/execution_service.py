"""User-owned execution history and approval execution operations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.executor.executor import EXECUTABLE_ACTIONS, ExecutionRequest, Executor
from backend.models.auth import User
from backend.models.finops import Approval, ApprovalEvent, Execution, FinOpsReport, Resource, ScanResourceSnapshot
from backend.schemas.execution import ExecutionItem, ExecutionTriggerResponse
from workflow.models import ApprovalRecord

logger = logging.getLogger(__name__)


class ExecutionService:
    """Execute only an authenticated user's approved database records."""

    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = executor or Executor()

    def list_executions(self, db: Session, user_id: int) -> list[ExecutionItem]:
        rows = db.execute(
            select(Execution, Approval, Resource)
            .join(Approval, (Approval.approval_id == Execution.approval_id) & (Approval.user_id == Execution.user_id) & (Approval.scan_id == Execution.scan_id))
            .join(ScanResourceSnapshot, (ScanResourceSnapshot.snapshot_id == Execution.snapshot_id) & (ScanResourceSnapshot.user_id == Execution.user_id) & (ScanResourceSnapshot.scan_id == Execution.scan_id))
            .join(Resource, (Resource.resource_id == ScanResourceSnapshot.resource_id) & (Resource.user_id == ScanResourceSnapshot.user_id))
            .where(Execution.user_id == user_id)
            .order_by(Execution.created_at.desc())
        ).all()
        items = [self._to_item(record, approval, resource.external_id, self._risk_data(db, user_id, approval.scan_id, resource.external_id)) for record, approval, resource in rows]
        already_executed = {item.approval_id for item in items}
        pending = db.execute(
            select(Approval, Resource)
            .join(ScanResourceSnapshot, (ScanResourceSnapshot.snapshot_id == Approval.snapshot_id) & (ScanResourceSnapshot.user_id == Approval.user_id) & (ScanResourceSnapshot.scan_id == Approval.scan_id))
            .join(Resource, (Resource.resource_id == ScanResourceSnapshot.resource_id) & (Resource.user_id == ScanResourceSnapshot.user_id))
            .where(Approval.user_id == user_id, Approval.status == "approved")
        ).all()
        for approval, resource in pending:
            if approval.approval_id not in already_executed and approval.action in EXECUTABLE_ACTIONS:
                items.append(self._pending_item(approval, resource.external_id, self._risk_data(db, user_id, approval.scan_id, resource.external_id)))
        return sorted(items, key=lambda item: item.timestamp, reverse=True)

    def get_execution(self, db: Session, user_id: int, execution_id: str) -> ExecutionItem | None:
        if execution_id.startswith("pending-"):
            approval_id = execution_id.removeprefix("pending-")
            pair = db.execute(
                select(Approval, Resource)
                .join(ScanResourceSnapshot, (ScanResourceSnapshot.snapshot_id == Approval.snapshot_id) & (ScanResourceSnapshot.user_id == Approval.user_id) & (ScanResourceSnapshot.scan_id == Approval.scan_id))
                .join(Resource, (Resource.resource_id == ScanResourceSnapshot.resource_id) & (Resource.user_id == ScanResourceSnapshot.user_id))
                .where(Approval.user_id == user_id, Approval.approval_id == approval_id, Approval.status == "approved")
            ).first()
            return self._pending_item(pair[0], pair[1].external_id, self._risk_data(db, user_id, pair[0].scan_id, pair[1].external_id)) if pair else None
        row = db.execute(
            select(Execution, Approval, Resource)
            .join(Approval, (Approval.approval_id == Execution.approval_id) & (Approval.user_id == Execution.user_id) & (Approval.scan_id == Execution.scan_id))
            .join(ScanResourceSnapshot, (ScanResourceSnapshot.snapshot_id == Execution.snapshot_id) & (ScanResourceSnapshot.user_id == Execution.user_id) & (ScanResourceSnapshot.scan_id == Execution.scan_id))
            .join(Resource, (Resource.resource_id == ScanResourceSnapshot.resource_id) & (Resource.user_id == ScanResourceSnapshot.user_id))
            .where(Execution.user_id == user_id, Execution.execution_id == execution_id)
        ).first()
        return self._to_item(row[0], row[1], row[2].external_id, self._risk_data(db, user_id, row[1].scan_id, row[2].external_id)) if row else None

    def execute_approval(self, db: Session, approval_id: str, user: User) -> ExecutionTriggerResponse:
        approval = db.scalar(
            select(Approval).where(Approval.user_id == user.id, Approval.approval_id == approval_id).with_for_update()
        )
        if approval is None:
            raise LookupError("Approval not found")
        if approval.status != "approved":
            raise ValueError(f"Approval {approval_id} is '{approval.status}' — only approved requests can be executed.")
        if approval.action not in EXECUTABLE_ACTIONS:
            raise ValueError(f"Action '{approval.action}' is not executable by the Executor.")
        if db.scalar(select(Execution.execution_id).where(Execution.approval_id == approval_id, Execution.user_id == user.id)):
            raise ValueError(f"Approval {approval_id} has already been executed.")

        resource = db.scalar(
            select(Resource).join(ScanResourceSnapshot,
                (ScanResourceSnapshot.resource_id == Resource.resource_id) & (ScanResourceSnapshot.user_id == Resource.user_id))
            .where(ScanResourceSnapshot.snapshot_id == approval.snapshot_id, ScanResourceSnapshot.user_id == user.id, ScanResourceSnapshot.scan_id == approval.scan_id)
        )
        if resource is None:
            raise LookupError("Approval resource not found")
        approval_record = ApprovalRecord(
            approval_id=approval.approval_id, resource_id=resource.external_id, action=approval.action,
            risk_level=approval.risk_level or "unknown", estimated_savings=float(approval.estimated_savings or 0),
            business_justification=approval.business_justification or "", execution_steps=list(approval.execution_steps or []),
            status="approved", created_at=approval.created_at, updated_at=approval.updated_at,
        )
        risk_context = self._risk_data(db, user.id, approval.scan_id, resource.external_id)
        result = self._executor.execute(ExecutionRequest.from_approval_record(approval_record))
        logs = result.log_path.read_text(encoding="utf-8").splitlines() if result.log_path.exists() else []
        completed_at = datetime.now(timezone.utc)
        execution = Execution(
            execution_id=result.execution_id, user_id=user.id, scan_id=approval.scan_id,
            approval_id=approval.approval_id, snapshot_id=approval.snapshot_id,
            action=approval.action, status=result.status, mode=result.mode,
            result_data={"resource_id": resource.external_id, "log_path": str(result.log_path), **risk_context},
            log_lines=logs, rollback_steps=list(result.rollback_plan.steps), error_message=result.error_message,
            completed_at=completed_at,
        )
        db.add(execution)
        if result.status == "success":
            approval.status = "executed"
            approval.updated_at = completed_at
            db.add(ApprovalEvent(
                user_id=user.id, scan_id=approval.scan_id, approval_id=approval.approval_id,
                actor_user_id=user.id, previous_status="approved", new_status="executed",
                notes=f"Executed via API in {result.mode} mode.",
            ))
        db.commit()
        logger.info("Execution %s completed with status=%s", result.execution_id, result.status)
        return ExecutionTriggerResponse(
            execution_id=result.execution_id, approval_id=approval.approval_id,
            resource_id=resource.external_id, action=approval.action, status=result.status,
            mode=result.mode, log_path=str(result.log_path),
            message="Remediation executed successfully." if result.status == "success" else f"Remediation failed: {result.error_message}",
        )

    @staticmethod
    def _risk_data(db: Session, user_id: int, scan_id: str, resource_id: str) -> dict:
        report = db.scalar(select(FinOpsReport).where(
            FinOpsReport.user_id == user_id, FinOpsReport.scan_id == scan_id,
            FinOpsReport.report_type == "risk_assessments",
        ))
        if not report:
            return {}
        for row in report.report_data.get("items", []):
            if str(row.get("resource_id")) == resource_id:
                return {key: row[key] for key in ("risk_score", "risk_explanation") if key in row}
        return {}

    @staticmethod
    def _to_item(record: Execution, approval: Approval, resource_id: str, risk: dict) -> ExecutionItem:
        context = record.result_data or {}
        context = {**risk, **context}
        return ExecutionItem(
            execution_id=record.execution_id, approval_id=approval.approval_id,
            resource_id=resource_id, action=record.action, status=record.status,
            timestamp=record.created_at.isoformat(), estimated_savings=float(approval.estimated_savings or 0),
            mode=record.mode, execution_steps=list(approval.execution_steps or []),
            rollback_steps=list(record.rollback_steps or []), risk_level=approval.risk_level,
            risk_score=context.get("risk_score"), risk_explanation=context.get("risk_explanation"),
            logs=list(record.log_lines or []), error_message=record.error_message,
        )

    @staticmethod
    def _pending_item(approval: Approval, resource_id: str, risk: dict) -> ExecutionItem:
        return ExecutionItem(
            execution_id=f"pending-{approval.approval_id}", approval_id=approval.approval_id,
            resource_id=resource_id, action=approval.action, status="pending",
            timestamp=approval.updated_at.isoformat(), estimated_savings=float(approval.estimated_savings or 0),
            mode="simulation", execution_steps=list(approval.execution_steps or []),
            risk_level=approval.risk_level, risk_score=risk.get("risk_score"),
            risk_explanation=risk.get("risk_explanation"), logs=[],
        )
