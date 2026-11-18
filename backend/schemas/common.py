"""Shared Pydantic schemas for API responses."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy", examples=["healthy"])
    deployment: Literal["local", "hosted"] = "local"
    aws_scan_enabled: bool = True
    execution_mode: str = "simulation"
    revision: str | None = None


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list wrapper."""

    count: int
    items: list[T]
