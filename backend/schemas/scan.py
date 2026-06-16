"""Cloud scan orchestration schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ScanStatus = str  # running | completed | failed | idle
ScanMode = Literal["synthetic", "aws"]


class ScanStepProgress(BaseModel):
    name: str
    status: str  # pending | running | completed | failed


class ScanStartRequest(BaseModel):
    mode: ScanMode = Field(
        default="synthetic",
        description="Discovery mode: synthetic (default) or live AWS via Scout Agent.",
    )


class ScanStartResponse(BaseModel):
    scan_id: str
    status: str
    message: str
    scan_mode: ScanMode = "synthetic"


class ScanStatusResponse(BaseModel):
    scan_id: str | None = None
    status: str
    progress: int
    scan_mode: ScanMode | None = None
    current_step: str | None = None
    steps: list[ScanStepProgress] = []
    message: str | None = None
    error: str | None = None
