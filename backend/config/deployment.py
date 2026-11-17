"""Deployment helpers for local vs hosted (Render) environments."""

from __future__ import annotations

import os


def is_hosted_deployment() -> bool:
    """True when running on Render or explicit hosted flag."""
    if os.getenv("DEPLOYMENT_ENV", "").lower() in {"production", "hosted"}:
        return True
    return os.getenv("RENDER") == "true" or bool(os.getenv("RAILWAY_ENVIRONMENT"))


def aws_scan_enabled() -> bool:
    """Whether live AWS discovery scans are permitted."""
    override = os.getenv("ALLOW_AWS_SCAN", "").strip().lower()
    if override in {"1", "true", "yes"}:
        return True
    if override in {"0", "false", "no"}:
        return False
    return not is_hosted_deployment()


def cors_allow_origins() -> list[str]:
    """Parse CORS origins — required for Vercel → Render in production."""
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]


def execution_mode() -> str:
    """Return configured execution mode (simulation by default)."""
    return os.getenv("EXECUTION_MODE", "simulation").strip().lower() or "simulation"
