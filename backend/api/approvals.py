"""Approval workflow endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_approval_service
from backend.schemas.approvals import ApprovalActionRequest, ApprovalItem
from backend.schemas.common import PaginatedResponse
from backend.services.approval_service import ApprovalService

router = APIRouter(tags=["Approvals"])


@router.get(
    "/approvals",
    response_model=PaginatedResponse[ApprovalItem],
    summary="List approval queue",
)
def list_approvals(
    service: ApprovalService = Depends(get_approval_service),
) -> PaginatedResponse[ApprovalItem]:
    """Return all approval workflow records."""
    items = service.list_approvals()
    return PaginatedResponse[ApprovalItem](count=len(items), items=items)


@router.post(
    "/approve/{approval_id}",
    response_model=ApprovalItem,
    summary="Approve a remediation plan",
)
def approve_remediation(
    approval_id: str,
    payload: ApprovalActionRequest | None = None,
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalItem:
    """Approve a pending remediation request."""
    request = payload or ApprovalActionRequest()
    try:
        return service.approve(
            approval_id,
            reviewer=request.reviewer,
            notes=request.notes,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/reject/{approval_id}",
    response_model=ApprovalItem,
    summary="Reject a remediation plan",
)
def reject_remediation(
    approval_id: str,
    payload: ApprovalActionRequest | None = None,
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalItem:
    """Reject a pending remediation request."""
    request = payload or ApprovalActionRequest()
    try:
        return service.reject(
            approval_id,
            reviewer=request.reviewer,
            notes=request.notes,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
