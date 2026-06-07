"""Remediation execution service."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agents.executor.execution_history import ExecutionHistoryStore, ExecutionRecord, utc_now
from agents.executor.executor import EXECUTABLE_ACTIONS, ExecutionRequest, Executor
from workflow.approval_manager import ApprovalManager
from workflow.approval_queue import ApprovalNotFoundError
from workflow.models import ApprovalRecord

from backend.models.paths import (
    EXECUTION_LOGS_DIR,
    PROJECT_ROOT,
    RISK_ASSESSMENT_CSV,
    ROLLBACK_PLANS_JSON,
)
from backend.schemas.execution import ExecutionItem, ExecutionTriggerResponse
from backend.services.data_loader import DataLoader

logger = logging.getLogger(__name__)

EXECUTOR_RESULTS_DIR = PROJECT_ROOT / "agents" / "executor" / "results"


class ExecutionService:
    """Bridge the executor agent to REST API operations."""

    def __init__(
        self,
        executor: Executor | None = None,
        approval_manager: ApprovalManager | None = None,
        history_store: ExecutionHistoryStore | None = None,
        loader: DataLoader | None = None,
    ) -> None:
        self._executor = executor or Executor()
        self._approval_manager = approval_manager or ApprovalManager()
        self._history_store = history_store or ExecutionHistoryStore(EXECUTOR_RESULTS_DIR)
        self._loader = loader or DataLoader()

    def list_executions(self) -> list[ExecutionItem]:
        """Return remediation execution history enriched with workflow and risk context."""
        records = self._history_store.load_records()
        approvals = {
            item.approval_id: item for item in self._approval_manager.queue.load_records()
        }
        rollbacks = self._load_rollback_plans()
        risk_map = {
            row["resource_id"]: row
            for row in self._loader.read_csv(RISK_ASSESSMENT_CSV)
        }

        items = [
            self._to_execution_item(record, approvals, rollbacks, risk_map)
            for record in records
        ]

        executed_approvals = {record.approval_id for record in records}
        for approval in approvals.values():
            if approval.status != "approved":
                continue
            if approval.approval_id in executed_approvals:
                continue
            if approval.action not in EXECUTABLE_ACTIONS:
                continue
            items.append(self._pending_execution_item(approval, risk_map, rollbacks))

        items.sort(key=lambda item: item.timestamp, reverse=True)
        return items

    def get_execution(self, execution_id: str) -> ExecutionItem | None:
        """Return a single execution record by identifier."""
        for item in self.list_executions():
            if item.execution_id == execution_id:
                return item
        return None

    def execute_approval(self, approval_id: str) -> ExecutionTriggerResponse:
        """
        Trigger execution for a single approved remediation request.

        Args:
            approval_id: Approved workflow request identifier.

        Returns:
            ExecutionTriggerResponse with execution outcome metadata.
        """
        try:
            approval = self._approval_manager.get_request(approval_id)
        except ApprovalNotFoundError as exc:
            raise LookupError(str(exc)) from exc

        if approval.status != "approved":
            raise ValueError(
                f"Approval {approval_id} is '{approval.status}' — only approved requests can be executed."
            )

        if approval.action not in EXECUTABLE_ACTIONS:
            raise ValueError(
                f"Action '{approval.action}' is not executable by the Executor."
            )

        if self._history_store.get_by_approval_id(approval_id):
            raise ValueError(f"Approval {approval_id} has already been executed.")

        request = ExecutionRequest.from_approval_record(approval)
        result = self._executor.execute(request)

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
                approval_id,
                notes=f"Executed via API in {result.mode} mode.",
            )

        logger.info(
            "Executed approval %s with status=%s",
            approval_id,
            result.status,
        )

        return ExecutionTriggerResponse(
            execution_id=result.execution_id,
            approval_id=approval_id,
            resource_id=result.request.resource_id,
            action=result.request.action,
            status=result.status,
            mode=result.mode,
            log_path=str(result.log_path),
            message=(
                "Remediation executed successfully."
                if result.status == "success"
                else f"Remediation failed: {result.error_message}"
            ),
        )

    def _load_rollback_plans(self) -> dict[str, list[str]]:
        """Load rollback steps keyed by approval ID."""
        if not ROLLBACK_PLANS_JSON.exists():
            return {}

        with open(ROLLBACK_PLANS_JSON, encoding="utf-8") as handle:
            payload = json.load(handle)

        return {
            str(item["approval_id"]): list(item.get("steps", []))
            for item in payload
        }

    def _read_logs(self, execution_id: str) -> list[str]:
        """Read persisted execution log lines."""
        log_path = EXECUTION_LOGS_DIR / f"execution_{execution_id}.log"
        if not log_path.exists():
            return []

        return [
            line.rstrip("\n")
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _to_execution_item(
        self,
        record: ExecutionRecord,
        approvals: dict[str, ApprovalRecord],
        rollbacks: dict[str, list[str]],
        risk_map: dict[str, dict[str, object]],
    ) -> ExecutionItem:
        approval = approvals.get(record.approval_id)
        risk = risk_map.get(record.resource_id, {})

        return ExecutionItem(
            execution_id=record.execution_id,
            approval_id=record.approval_id,
            resource_id=record.resource_id,
            action=record.action,
            status=record.status,
            timestamp=(
                record.timestamp.isoformat()
                if hasattr(record.timestamp, "isoformat")
                else str(record.timestamp)
            ),
            estimated_savings=float(approval.estimated_savings) if approval else 0.0,
            mode=record.mode,
            execution_steps=list(approval.execution_steps) if approval else [],
            rollback_steps=rollbacks.get(record.approval_id, []),
            risk_level=str(risk.get("risk_level")) if risk.get("risk_level") else approval.risk_level if approval else None,
            risk_score=int(risk["risk_score"]) if risk.get("risk_score") is not None else None,
            risk_explanation=str(risk.get("risk_explanation")) if risk.get("risk_explanation") else None,
            logs=self._read_logs(record.execution_id),
            error_message=record.error_message,
        )

    def _pending_execution_item(
        self,
        approval: ApprovalRecord,
        risk_map: dict[str, dict[str, object]],
        rollbacks: dict[str, list[str]],
    ) -> ExecutionItem:
        risk = risk_map.get(approval.resource_id, {})
        return ExecutionItem(
            execution_id=f"pending-{approval.approval_id}",
            approval_id=approval.approval_id,
            resource_id=approval.resource_id,
            action=approval.action,
            status="pending",
            timestamp=approval.updated_at,
            estimated_savings=float(approval.estimated_savings),
            mode="simulation",
            execution_steps=list(approval.execution_steps),
            rollback_steps=rollbacks.get(approval.approval_id, []),
            risk_level=str(risk.get("risk_level")) if risk.get("risk_level") else approval.risk_level,
            risk_score=int(risk["risk_score"]) if risk.get("risk_score") is not None else None,
            risk_explanation=str(risk.get("risk_explanation")) if risk.get("risk_explanation") else None,
            logs=[],
            error_message=None,
        )
