"""Execution history schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ExecutionItem(BaseModel):
    """Remediation execution history record."""

    execution_id: str
    approval_id: str
    resource_id: str
    action: str
    status: str
    timestamp: str
    estimated_savings: float = 0.0
    mode: str = "simulation"
    execution_steps: list[str] = []
    rollback_steps: list[str] = []
    risk_level: str | None = None
    risk_score: int | None = None
    risk_explanation: str | None = None
    logs: list[str] = []
    error_message: str | None = None


class ExecutionTriggerResponse(BaseModel):
    """Response after triggering remediation execution."""

    execution_id: str
    approval_id: str
    resource_id: str
    action: str
    status: str
    mode: str
    log_path: str | None = None
    message: str
