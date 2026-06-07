"""Remediation execution endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_execution_service
from backend.schemas.common import PaginatedResponse
from backend.schemas.execution import ExecutionItem, ExecutionTriggerResponse
from backend.services.execution_service import ExecutionService

router = APIRouter(tags=["Execution"])


@router.get(
    "/executions",
    response_model=PaginatedResponse[ExecutionItem],
    summary="List execution history",
)
def list_executions(
    service: ExecutionService = Depends(get_execution_service),
) -> PaginatedResponse[ExecutionItem]:
    """Return remediation execution history."""
    items = service.list_executions()
    return PaginatedResponse[ExecutionItem](count=len(items), items=items)


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionItem,
    summary="Get execution details",
)
def get_execution(
    execution_id: str,
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionItem:
    """Return a single remediation execution record."""
    item = service.get_execution(execution_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found.",
        )
    return item


@router.post(
    "/execute/{approval_id}",
    response_model=ExecutionTriggerResponse,
    summary="Execute an approved remediation plan",
)
def execute_remediation(
    approval_id: str,
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionTriggerResponse:
    """Trigger execution for a single approved remediation request."""
    try:
        return service.execute_approval(approval_id)
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
