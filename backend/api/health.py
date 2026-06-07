"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health_check() -> HealthResponse:
    """Return API health status."""
    return HealthResponse(status="healthy")
