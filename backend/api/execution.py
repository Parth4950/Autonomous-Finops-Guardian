"""Authenticated, user-owned remediation execution endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_execution_service
from backend.auth.dependencies import current_user_or_simulation as current_user
from backend.db.session import get_db
from backend.models.auth import User
from backend.schemas.common import PaginatedResponse
from backend.schemas.execution import ExecutionItem, ExecutionTriggerResponse
from backend.services.execution_service import ExecutionService

router = APIRouter(tags=["Execution"])


@router.get("/executions", response_model=PaginatedResponse[ExecutionItem], summary="List execution history")
def list_executions(
    db: Session = Depends(get_db), user: User = Depends(current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> PaginatedResponse[ExecutionItem]:
    items = service.list_executions(db, user.id)
    return PaginatedResponse[ExecutionItem](count=len(items), items=items)


@router.get("/executions/{execution_id}", response_model=ExecutionItem, summary="Get execution details")
def get_execution(
    execution_id: str, db: Session = Depends(get_db), user: User = Depends(current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionItem:
    item = service.get_execution(db, user.id, execution_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found.")
    return item


@router.post("/execute/{approval_id}", response_model=ExecutionTriggerResponse, summary="Execute an approved remediation plan")
def execute_remediation(
    approval_id: str, db: Session = Depends(get_db), user: User = Depends(current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionTriggerResponse:
    try:
        return service.execute_approval(db, approval_id, user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
