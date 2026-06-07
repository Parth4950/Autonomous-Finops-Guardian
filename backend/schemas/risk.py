"""Risk assessment schemas."""

from __future__ import annotations

from pydantic import BaseModel


class RiskAssessmentItem(BaseModel):
    """Risk assessment record for a cloud resource."""

    resource_id: str
    waste_score: float
    monthly_cost: float
    waste_probability: str
    environment: str
    business_critical: bool
    attached_to_load_balancer: bool
    member_of_autoscaling_group: bool
    owner_exists: bool
    recent_activity_days: int
    risk_score: int
    risk_level: str
    risk_explanation: str
    recommendation: str
