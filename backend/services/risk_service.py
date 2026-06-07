"""Risk assessment service."""

from __future__ import annotations

from backend.models.paths import RISK_ASSESSMENT_CSV
from backend.schemas.risk import RiskAssessmentItem
from backend.services.data_loader import DataLoader


class RiskService:
    """Expose risk assessment agent outputs."""

    def __init__(self, loader: DataLoader | None = None) -> None:
        self._loader = loader or DataLoader()

    def list_risk_assessments(self) -> list[RiskAssessmentItem]:
        """Return all risk assessment records."""
        records = self._loader.read_csv(RISK_ASSESSMENT_CSV)
        items: list[RiskAssessmentItem] = []

        for record in records:
            items.append(
                RiskAssessmentItem(
                    resource_id=str(record["resource_id"]),
                    waste_score=float(record["waste_score"]),
                    monthly_cost=float(record["monthly_cost"]),
                    waste_probability=str(record["waste_probability"]),
                    environment=str(record["environment"]),
                    business_critical=DataLoader.coerce_bool(record["business_critical"]),
                    attached_to_load_balancer=DataLoader.coerce_bool(
                        record["attached_to_load_balancer"]
                    ),
                    member_of_autoscaling_group=DataLoader.coerce_bool(
                        record["member_of_autoscaling_group"]
                    ),
                    owner_exists=DataLoader.coerce_bool(record["owner_exists"]),
                    recent_activity_days=int(record["recent_activity_days"]),
                    risk_score=int(record["risk_score"]),
                    risk_level=str(record["risk_level"]),
                    risk_explanation=str(record["risk_explanation"]),
                    recommendation=str(record["recommendation"]),
                )
            )

        return items
