"""Rollback planning for remediation execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

ExecutableAction = Literal["terminate", "resize", "stop", "snapshot_and_delete"]

ROLLBACK_TEMPLATES: dict[str, list[str]] = {
    "terminate": [
        "Restore snapshot",
        "Launch replacement instance",
        "Validate instance health",
        "Update routing and monitoring",
    ],
    "resize": [
        "Stop instance",
        "Revert instance type to previous size",
        "Restart instance",
        "Validate application performance",
    ],
    "stop": [
        "Start instance",
        "Validate instance health",
        "Confirm dependent services recovered",
    ],
    "snapshot_and_delete": [
        "Restore volume from snapshot",
        "Attach volume to target instance",
        "Validate data integrity",
    ],
}


@dataclass(frozen=True)
class RollbackPlan:
    """Structured rollback plan for a remediation action."""

    approval_id: str
    resource_id: str
    action: str
    steps: list[str]

    def to_dict(self) -> dict[str, str | list[str]]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "approval_id": self.approval_id,
            "resource_id": self.resource_id,
            "action": self.action,
            "steps": self.steps,
        }


class RollbackManager:
    """
    Generate deterministic rollback plans for executed remediation actions.

    Rollback plans are prepared before execution so operators can recover
    quickly if remediation causes unintended impact.
    """

    @staticmethod
    def generate_plan(
        approval_id: str,
        resource_id: str,
        action: str,
    ) -> RollbackPlan:
        """
        Generate a rollback plan for an approved remediation action.

        Args:
            approval_id: Linked approval request identifier.
            resource_id: Target cloud resource identifier.
            action: Remediation action type.

        Returns:
            RollbackPlan with ordered recovery steps.

        Raises:
            ValueError: When no rollback template exists for the action.
        """
        if action not in ROLLBACK_TEMPLATES:
            raise ValueError(f"No rollback template defined for action: {action}")

        plan = RollbackPlan(
            approval_id=approval_id,
            resource_id=resource_id,
            action=action,
            steps=list(ROLLBACK_TEMPLATES[action]),
        )
        logger.info(
            "Generated rollback plan for %s (%s) with %d step(s)",
            resource_id,
            action,
            len(plan.steps),
        )
        return plan

    def generate_batch(
        self,
        requests: list[tuple[str, str, str]],
    ) -> list[RollbackPlan]:
        """
        Generate rollback plans for multiple remediation requests.

        Args:
            requests: List of (approval_id, resource_id, action) tuples.

        Returns:
            List of RollbackPlan objects.
        """
        return [
            self.generate_plan(approval_id, resource_id, action)
            for approval_id, resource_id, action in requests
        ]
