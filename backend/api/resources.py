"""Resource discovery endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_resource_service
from backend.schemas.common import PaginatedResponse
from backend.schemas.resources import ResourceItem
from backend.services.data_loader import DataNotFoundError
from backend.services.resource_service import ResourceService

router = APIRouter(tags=["Resources"])


@router.get(
    "/resources",
    response_model=PaginatedResponse[ResourceItem],
    summary="List discovered cloud resources",
)
def list_resources(
    service: ResourceService = Depends(get_resource_service),
) -> PaginatedResponse[ResourceItem]:
    """Return Scout/synthetic pipeline resource inventory."""
    try:
        items = service.list_resources()
    except DataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PaginatedResponse[ResourceItem](count=len(items), items=items)
