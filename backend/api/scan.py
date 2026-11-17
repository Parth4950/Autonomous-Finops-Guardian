"""Cloud scan endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.auth.dependencies import current_user_or_simulation as current_user, is_simulation_user
from backend.api.deps import get_scan_service
from backend.db.session import get_db
from backend.models.auth import User
from backend.models.finops import FinOpsReport, Scan, ScanResourceSnapshot
from backend.schemas.scan import ScanStartRequest, ScanStartResponse, ScanStatusResponse, ScanStepProgress
from backend.services.scan_service import ScanConfigurationError, ScanInProgressError, ScanService

router = APIRouter(tags=["Scan"])


@router.post(
    "/scan/start",
    response_model=ScanStartResponse,
    summary="Start a cloud FinOps scan",
)
def start_scan(
    request: ScanStartRequest = ScanStartRequest(),
    service: ScanService = Depends(get_scan_service),
    user: User = Depends(current_user),
) -> ScanStartResponse:
    """Run the full discovery-to-planning pipeline in the background."""
    if is_simulation_user(user) and (request.mode != "synthetic" or request.aws_account_id is not None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulation mode only supports synthetic demo scans. Sign in to run live AWS scans.",
        )
    try:
        state = service.start_scan(
            user_id=user.id,
            mode=request.mode,
            aws_account_id=request.aws_account_id,
            region=request.region,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ScanInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ScanConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ScanStartResponse(
        scan_id=state.scan_id,
        status=state.status,
        message=state.message or "Scan started",
        scan_mode=state.scan_mode,
        aws_account_id=state.aws_account_id,
        region=state.region,
    )


@router.get(
    "/scan/status",
    response_model=ScanStatusResponse,
    summary="Get cloud scan progress",
)
def get_scan_status(
    service: ScanService = Depends(get_scan_service),
    user: User = Depends(current_user),
) -> ScanStatusResponse:
    """Return progress for the latest cloud scan."""
    state = service.get_status(user_id=user.id)
    if state is None:
        return ScanStatusResponse(status="idle", progress=0, message="No scan has been run yet")

    return ScanStatusResponse(
        scan_id=state.scan_id,
        status=state.status,
        progress=state.progress,
        scan_mode=state.scan_mode,
        current_step=state.current_step,
        steps=[ScanStepProgress(name=s["name"], status=s["status"]) for s in state.steps],
        message=state.message,
        error=state.error,
    )


@router.get(
    "/scan/source",
    summary="Get latest scan data source metadata",
)
def get_scan_source(
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> dict:
    """Return this user's latest scan source summary with the legacy shape."""
    scan = db.scalar(select(Scan).where(Scan.user_id == user.id).order_by(Scan.created_at.desc()).limit(1))
    if scan is None:
        return {"mode": "unknown", "resource_count": 0}
    count = db.scalar(select(func.count()).select_from(ScanResourceSnapshot).where(
        ScanResourceSnapshot.user_id == user.id, ScanResourceSnapshot.scan_id == scan.scan_id,
    )) or 0
    report = db.scalar(select(FinOpsReport).where(
        FinOpsReport.user_id == user.id, FinOpsReport.scan_id == scan.scan_id,
        FinOpsReport.report_type == "scan_source",
    ))
    if report:
        return dict(report.report_data)
    return {"mode": scan.mode, "resource_count": int(count)}
