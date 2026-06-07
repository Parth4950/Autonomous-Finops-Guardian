"""FastAPI route modules."""

from backend.api import (
    approvals,
    audit,
    execution,
    health,
    planner,
    resources,
    risk,
    waste,
)

__all__ = [
    "health",
    "resources",
    "waste",
    "risk",
    "audit",
    "planner",
    "approvals",
    "execution",
]
