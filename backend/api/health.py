"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.config import aws_scan_enabled, execution_mode, is_hosted_deployment
from backend.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health_check() -> HealthResponse:
    """Return API health status and deployment metadata."""
    return HealthResponse(
        status="healthy",
        deployment="hosted" if is_hosted_deployment() else "local",
        aws_scan_enabled=aws_scan_enabled(),
        execution_mode=execution_mode(),
    )
