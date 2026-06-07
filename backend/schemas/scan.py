"""Cloud scan orchestration schemas."""

from __future__ import annotations

from pydantic import BaseModel

ScanStatus = str  # running | completed | failed | idle


class ScanStepProgress(BaseModel):
    name: str
    status: str  # pending | running | completed | failed


class ScanStartResponse(BaseModel):
    scan_id: str
    status: str
    message: str


class ScanStatusResponse(BaseModel):
    scan_id: str | None = None
    status: str
    progress: int
    current_step: str | None = None
    steps: list[ScanStepProgress] = []
    message: str | None = None
    error: str | None = None
