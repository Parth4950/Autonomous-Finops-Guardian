"""User-owned PostgreSQL approval operations."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.auth import User
from backend.models.finops import Approval, ApprovalEvent, Resource, ScanResourceSnapshot
from backend.schemas.approvals import ApprovalItem


class ApprovalService:
    def list_approvals(self, db: Session, user_id: int) -> list[ApprovalItem]:
        rows = db.execute(
            select(Approval, Resource, User)
            .join(ScanResourceSnapshot, (ScanResourceSnapshot.snapshot_id == Approval.snapshot_id) & (ScanResourceSnapshot.user_id == Approval.user_id) & (ScanResourceSnapshot.scan_id == Approval.scan_id))
            .join(Resource, (Resource.resource_id == ScanResourceSnapshot.resource_id) & (Resource.user_id == ScanResourceSnapshot.user_id))
            .outerjoin(User, User.id == Approval.reviewed_by_user_id)
            .where(Approval.user_id == user_id)
            .order_by(Approval.created_at.desc())
        ).all()
        return [self._to_schema(approval, resource.external_id, reviewer.username if reviewer else None) for approval, resource, reviewer in rows]

    def approve(self, db: Session, approval_id: str, user: User, notes: str | None) -> ApprovalItem:
        return self._transition(db, approval_id, user, "approved", notes)

    def reject(self, db: Session, approval_id: str, user: User, notes: str | None) -> ApprovalItem:
        return self._transition(db, approval_id, user, "rejected", notes)

    def _transition(self, db: Session, approval_id: str, user: User, target: str, notes: str | None) -> ApprovalItem:
        row = db.scalar(select(Approval).where(Approval.approval_id == approval_id, Approval.user_id == user.id).with_for_update())
        if row is None:
            raise LookupError("Approval not found")
        if row.status != "pending":
            raise ValueError(f"Approval is '{row.status}' and cannot be {target}.")
        previous = row.status
        row.status = target
        row.reviewed_by_user_id = user.id
        row.review_notes = notes
        row.updated_at = datetime.now(timezone.utc)
        db.add(ApprovalEvent(
            user_id=user.id, scan_id=row.scan_id, approval_id=row.approval_id,
            actor_user_id=user.id, previous_status=previous, new_status=target, notes=notes,
        ))
        db.flush()
        result = self._schema_for_row(db, row)
        db.commit()
        return result

    def _schema_for_row(self, db: Session, row: Approval) -> ApprovalItem:
        resource = db.scalar(
            select(Resource).join(ScanResourceSnapshot,
                (ScanResourceSnapshot.resource_id == Resource.resource_id) & (ScanResourceSnapshot.user_id == Resource.user_id))
            .where(ScanResourceSnapshot.snapshot_id == row.snapshot_id, ScanResourceSnapshot.user_id == row.user_id, ScanResourceSnapshot.scan_id == row.scan_id)
        )
        reviewer = db.get(User, row.reviewed_by_user_id) if row.reviewed_by_user_id else None
        if resource is None:
            raise LookupError("Approval resource not found")
        return self._to_schema(row, resource.external_id, reviewer.username if reviewer else None)

    @staticmethod
    def _to_schema(row: Approval, resource_id: str, reviewer: str | None) -> ApprovalItem:
        return ApprovalItem(
            approval_id=row.approval_id, resource_id=resource_id, action=row.action,
            risk_level=row.risk_level or "unknown", estimated_savings=float(row.estimated_savings or 0),
            business_justification=row.business_justification or "", execution_steps=list(row.execution_steps or []),
            status=row.status, created_at=row.created_at.isoformat(), updated_at=row.updated_at.isoformat(),
            reviewed_by=reviewer, review_notes=row.review_notes,
        )
