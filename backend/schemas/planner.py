"""Remediation planning schemas."""

from __future__ import annotations

from pydantic import BaseModel


class RemediationPlanItem(BaseModel):
    """Planner remediation plan record."""

    resource_id: str
    action: str
    risk_level: str
    estimated_savings: float
    execution_steps: str
    business_justification: str
    resource_type: str | None = None
    waste_score: float | None = None
    recommendation: str | None = None
    technical_justification: str | None = None
    expected_outcome: str | None = None
    risk_explanation: str | None = None
    risk_score: int | None = None
    monthly_cost: float | None = None
    annual_cost: float | None = None
