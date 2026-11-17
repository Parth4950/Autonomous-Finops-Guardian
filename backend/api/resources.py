"""Authenticated resource inventory endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.dependencies import current_user
from backend.db.session import get_db
from backend.models.auth import User
from backend.models.finops import Resource, ScanResourceSnapshot
from backend.schemas.common import PaginatedResponse
from backend.schemas.resources import ResourceItem
from backend.services.data_loader import DataNotFoundError
from backend.services.owned_scan_data import latest_completed_scan

router = APIRouter(tags=["Resources"])


@router.get("/resources", response_model=PaginatedResponse[ResourceItem], summary="List discovered cloud resources")
def list_resources(
    db: Session = Depends(get_db), user: User = Depends(current_user),
) -> PaginatedResponse[ResourceItem]:
    """Return resources from this user's latest completed scan only."""
    try:
        scan = latest_completed_scan(db, user.id)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    rows = db.execute(
        select(ScanResourceSnapshot, Resource)
        .join(Resource, (Resource.resource_id == ScanResourceSnapshot.resource_id) & (Resource.user_id == ScanResourceSnapshot.user_id))
        .where(ScanResourceSnapshot.user_id == user.id, ScanResourceSnapshot.scan_id == scan.scan_id)
        .order_by(ScanResourceSnapshot.snapshot_id)
    ).all()
    items = [ResourceItem(
        resource_id=resource.external_id,
        avg_cpu=float(snapshot.avg_cpu or 0),
        avg_network_in=float(snapshot.avg_network_in or 0),
        avg_network_out=float(snapshot.avg_network_out or 0),
        monthly_cost=float(snapshot.estimated_monthly_cost or 0),
        resource_label=snapshot.resource_label or "unknown",
    ) for snapshot, resource in rows]
    return PaginatedResponse[ResourceItem](count=len(items), items=items)
