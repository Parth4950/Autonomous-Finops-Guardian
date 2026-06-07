"""Approval workflow schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApprovalItem(BaseModel):
    """Approval queue record."""

    approval_id: str
    resource_id: str
    action: str
    risk_level: str
    estimated_savings: float
    business_justification: str
    execution_steps: list[str]
    status: str
    created_at: str
    updated_at: str
    reviewed_by: str | None = None
    review_notes: str | None = None


class ApprovalActionRequest(BaseModel):
    """Optional payload for approve/reject actions."""

    reviewer: str = Field(default="api-user", examples=["cloud-engineer"])
    notes: str | None = Field(default=None, examples=["Approved via dashboard"])
