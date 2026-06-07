"""Financial audit endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_audit_service
from backend.schemas.audit import AuditResultItem, ExecutiveReport
from backend.schemas.common import PaginatedResponse
from backend.services.audit_service import AuditService
from backend.services.data_loader import DataNotFoundError

router = APIRouter(tags=["Audit"])


@router.get(
    "/audit",
    response_model=PaginatedResponse[AuditResultItem],
    summary="List auditor results",
)
def list_audit_results(
    service: AuditService = Depends(get_audit_service),
) -> PaginatedResponse[AuditResultItem]:
    """Return financial audit and savings analysis results."""
    try:
        items = service.list_audit_results()
    except DataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PaginatedResponse[AuditResultItem](count=len(items), items=items)


@router.get(
    "/audit/report",
    response_model=ExecutiveReport,
    summary="Get executive audit report",
)
def get_executive_report(
    service: AuditService = Depends(get_audit_service),
) -> ExecutiveReport:
    """Return the Gemini-generated executive summary report."""
    try:
        return service.get_executive_report()
    except DataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
