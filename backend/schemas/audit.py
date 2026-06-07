"""Financial audit schemas."""

from __future__ import annotations

from pydantic import BaseModel


class AuditResultItem(BaseModel):
    """Auditor financial analysis record."""

    resource_id: str
    resource_type: str
    monthly_cost: float
    annual_cost: float
    waste_score: float
    risk_level: str
    priority_score: float
    priority_category: str
    potential_monthly_savings: float
    potential_annual_savings: float
    recommendation: str


class ExecutiveReport(BaseModel):
    """Gemini-generated executive audit summary."""

    executive_summary: str
    key_findings: list[str]
    top_cost_drivers: list[str]
    recommended_actions: list[str]
    risk_considerations: list[str]
    estimated_savings: dict[str, float]
    source: str
