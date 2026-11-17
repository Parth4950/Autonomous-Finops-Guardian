"""Authenticated, user-owned approval workflow endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import current_user_or_simulation as current_user
from backend.db.session import get_db
from backend.models.auth import User
from backend.schemas.approvals import ApprovalActionRequest, ApprovalItem
from backend.schemas.common import PaginatedResponse
from backend.services.approval_service import ApprovalService

router = APIRouter(tags=["Approvals"])
service = ApprovalService()


@router.get("/approvals", response_model=PaginatedResponse[ApprovalItem], summary="List approval queue")
def list_approvals(db: Session = Depends(get_db), user: User = Depends(current_user)) -> PaginatedResponse[ApprovalItem]:
    items = service.list_approvals(db, user.id)
    return PaginatedResponse[ApprovalItem](count=len(items), items=items)


@router.post("/approve/{approval_id}", response_model=ApprovalItem, summary="Approve a remediation plan")
def approve_remediation(
    approval_id: str, payload: ApprovalActionRequest | None = None,
    db: Session = Depends(get_db), user: User = Depends(current_user),
) -> ApprovalItem:
    try:
        return service.approve(db, approval_id, user, (payload.notes if payload else None))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/reject/{approval_id}", response_model=ApprovalItem, summary="Reject a remediation plan")
def reject_remediation(
    approval_id: str, payload: ApprovalActionRequest | None = None,
    db: Session = Depends(get_db), user: User = Depends(current_user),
) -> ApprovalItem:
    try:
        return service.reject(db, approval_id, user, (payload.notes if payload else None))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
