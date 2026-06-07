"""Approval workflow service."""

from __future__ import annotations

import logging

from workflow.approval_manager import ApprovalManager, ApprovalWorkflowError
from workflow.approval_queue import ApprovalNotFoundError
from workflow.models import ApprovalRecord

from backend.schemas.approvals import ApprovalItem

logger = logging.getLogger(__name__)


class ApprovalService:
    """Bridge the approval workflow to REST API operations."""

    def __init__(self, manager: ApprovalManager | None = None) -> None:
        self._manager = manager or ApprovalManager()

    def list_approvals(self) -> list[ApprovalItem]:
        """Return all approval queue records."""
        records = self._manager.queue.load_records()
        return [self._to_schema(record) for record in records]

    def approve(self, approval_id: str, reviewer: str, notes: str | None) -> ApprovalItem:
        """Approve a pending remediation request."""
        try:
            record = self._manager.approve_request(
                approval_id,
                reviewer=reviewer,
                notes=notes,
            )
            logger.info("Approved request %s via API", approval_id)
            return self._to_schema(record)
        except ApprovalNotFoundError as exc:
            raise LookupError(str(exc)) from exc
        except ApprovalWorkflowError as exc:
            raise ValueError(str(exc)) from exc

    def reject(self, approval_id: str, reviewer: str, notes: str | None) -> ApprovalItem:
        """Reject a pending remediation request."""
        try:
            record = self._manager.reject_request(
                approval_id,
                reviewer=reviewer,
                notes=notes,
            )
            logger.info("Rejected request %s via API", approval_id)
            return self._to_schema(record)
        except ApprovalNotFoundError as exc:
            raise LookupError(str(exc)) from exc
        except ApprovalWorkflowError as exc:
            raise ValueError(str(exc)) from exc

    @staticmethod
    def _to_schema(record: ApprovalRecord) -> ApprovalItem:
        payload = record.to_dict()
        return ApprovalItem.model_validate(payload)
