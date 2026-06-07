"""Cloud scan endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_scan_service
from backend.schemas.scan import ScanStartResponse, ScanStatusResponse, ScanStepProgress
from backend.services.scan_service import ScanInProgressError, ScanService

router = APIRouter(tags=["Scan"])


@router.post(
    "/scan/start",
    response_model=ScanStartResponse,
    summary="Start a cloud FinOps scan",
)
def start_scan(service: ScanService = Depends(get_scan_service)) -> ScanStartResponse:
    """Run the full discovery-to-planning pipeline in the background."""
    try:
        state = service.start_scan()
    except ScanInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ScanStartResponse(
        scan_id=state.scan_id,
        status=state.status,
        message=state.message or "Scan started",
    )


@router.get(
    "/scan/status",
    response_model=ScanStatusResponse,
    summary="Get cloud scan progress",
)
def get_scan_status(service: ScanService = Depends(get_scan_service)) -> ScanStatusResponse:
    """Return progress for the latest cloud scan."""
    state = service.get_status()
    if state is None:
        return ScanStatusResponse(status="idle", progress=0, message="No scan has been run yet")

    return ScanStatusResponse(
        scan_id=state.scan_id,
        status=state.status,
        progress=state.progress,
        current_step=state.current_step,
        steps=[ScanStepProgress(name=s["name"], status=s["status"]) for s in state.steps],
        message=state.message,
        error=state.error,
    )
