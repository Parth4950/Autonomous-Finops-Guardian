"""Remediation planning service."""

from __future__ import annotations

from backend.models.paths import REMEDIATION_PLAN_CSV
from backend.schemas.planner import RemediationPlanItem
from backend.services.data_loader import DataLoader


class PlannerService:
    """Expose planner agent remediation plans."""

    def __init__(self, loader: DataLoader | None = None) -> None:
        self._loader = loader or DataLoader()

    def list_plans(self) -> list[RemediationPlanItem]:
        """Return all remediation plans."""
        records = self._loader.read_csv(REMEDIATION_PLAN_CSV)
        return [RemediationPlanItem.model_validate(record) for record in records]
