"""Financial audit service."""

from __future__ import annotations

import json

from backend.models.paths import AUDIT_RESULTS_CSV, EXECUTIVE_REPORT_JSON
from backend.schemas.audit import AuditResultItem, ExecutiveReport
from backend.services.data_loader import DataLoader, DataNotFoundError


class AuditService:
    """Expose auditor agent outputs."""

    def __init__(self, loader: DataLoader | None = None) -> None:
        self._loader = loader or DataLoader()

    def list_audit_results(self) -> list[AuditResultItem]:
        """Return all financial audit records."""
        records = self._loader.read_csv(AUDIT_RESULTS_CSV)
        return [AuditResultItem.model_validate(record) for record in records]

    def get_executive_report(self) -> ExecutiveReport:
        """Return the Gemini-generated executive audit report."""
        if not EXECUTIVE_REPORT_JSON.exists():
            raise DataNotFoundError(
                f"Executive report not found at {EXECUTIVE_REPORT_JSON}. "
                "Run agents/auditor/auditor.py first."
            )
        payload = json.loads(EXECUTIVE_REPORT_JSON.read_text(encoding="utf-8"))
        return ExecutiveReport.model_validate(payload)
