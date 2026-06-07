"""Data models for the Human Approval Workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ApprovalStatus = Literal["pending", "approved", "rejected", "executed"]

RemediationAction = Literal[
    "terminate",
    "resize",
    "stop",
    "snapshot_and_delete",
    "manual_review",
    "ignore",
]

ACTIONS_REQUIRING_APPROVAL: frozenset[str] = frozenset(
    {
        "terminate",
        "resize",
        "stop",
        "snapshot_and_delete",
        "manual_review",
    }
)


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def format_timestamp(value: datetime) -> str:
    """Format a datetime as an ISO-8601 UTC string."""
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class ApprovalPackage:
    """Input package produced by the Planner Agent."""

    resource_id: str
    action: str
    risk_level: str
    estimated_savings: float
    business_justification: str
    execution_steps: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ApprovalPackage:
        """Build an approval package from a JSON/dict payload."""
        return cls(
            resource_id=str(payload["resource_id"]),
            action=str(payload["action"]),
            risk_level=str(payload["risk_level"]),
            estimated_savings=float(payload["estimated_savings"]),
            business_justification=str(payload["business_justification"]),
            execution_steps=[str(step) for step in payload["execution_steps"]],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return asdict(self)

    @property
    def requires_approval(self) -> bool:
        """Return True when this package represents an actionable remediation."""
        return self.action in ACTIONS_REQUIRING_APPROVAL


@dataclass
class ApprovalRecord:
    """Persisted approval request with governance metadata."""

    approval_id: str
    resource_id: str
    action: str
    risk_level: str
    estimated_savings: float
    business_justification: str
    execution_steps: list[str]
    status: ApprovalStatus
    created_at: datetime
    updated_at: datetime
    reviewed_by: str | None = None
    review_notes: str | None = None

    @classmethod
    def from_package(
        cls,
        package: ApprovalPackage,
        approval_id: str,
        *,
        created_at: datetime | None = None,
    ) -> ApprovalRecord:
        """Create a pending approval record from a planner package."""
        timestamp = created_at or utc_now()
        return cls(
            approval_id=approval_id,
            resource_id=package.resource_id,
            action=package.action,
            risk_level=package.risk_level,
            estimated_savings=package.estimated_savings,
            business_justification=package.business_justification,
            execution_steps=list(package.execution_steps),
            status="pending",
            created_at=timestamp,
            updated_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "approval_id": self.approval_id,
            "resource_id": self.resource_id,
            "action": self.action,
            "risk_level": self.risk_level,
            "estimated_savings": self.estimated_savings,
            "business_justification": self.business_justification,
            "execution_steps": self.execution_steps,
            "status": self.status,
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
            "reviewed_by": self.reviewed_by,
            "review_notes": self.review_notes,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ApprovalRecord:
        """Build an approval record from persisted storage."""
        return cls(
            approval_id=str(payload["approval_id"]),
            resource_id=str(payload["resource_id"]),
            action=str(payload["action"]),
            risk_level=str(payload["risk_level"]),
            estimated_savings=float(payload["estimated_savings"]),
            business_justification=str(payload["business_justification"]),
            execution_steps=[str(step) for step in payload["execution_steps"]],
            status=payload["status"],  # type: ignore[arg-type]
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            updated_at=datetime.fromisoformat(str(payload["updated_at"])),
            reviewed_by=payload.get("reviewed_by"),
            review_notes=payload.get("review_notes"),
        )

    def to_export_row(self) -> dict[str, Any]:
        """Return the CSV export columns for this record."""
        return {
            "approval_id": self.approval_id,
            "resource_id": self.resource_id,
            "action": self.action,
            "status": self.status,
            "timestamp": format_timestamp(self.updated_at),
        }


@dataclass(frozen=True)
class ApprovalHistoryEvent:
    """Audit trail entry for approval state transitions."""

    approval_id: str
    resource_id: str
    previous_status: ApprovalStatus | None
    new_status: ApprovalStatus
    timestamp: datetime
    actor: str
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "approval_id": self.approval_id,
            "resource_id": self.resource_id,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "timestamp": format_timestamp(self.timestamp),
            "actor": self.actor,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ApprovalHistoryEvent:
        """Build a history event from persisted storage."""
        return cls(
            approval_id=str(payload["approval_id"]),
            resource_id=str(payload["resource_id"]),
            previous_status=payload.get("previous_status"),  # type: ignore[arg-type]
            new_status=payload["new_status"],  # type: ignore[arg-type]
            timestamp=datetime.fromisoformat(str(payload["timestamp"])),
            actor=str(payload["actor"]),
            notes=payload.get("notes"),
        )


@dataclass(frozen=True)
class ApprovalSummary:
    """Aggregate approval workflow metrics."""

    total_requests: int
    pending: int
    approved: int
    rejected: int
    executed: int
    pending_savings: float
    approved_savings: float
