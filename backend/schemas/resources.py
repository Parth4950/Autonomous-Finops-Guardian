"""Resource discovery schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResourceItem(BaseModel):
    """Cloud resource inventory record."""

    resource_id: str
    avg_cpu: float
    avg_network_in: float
    avg_network_out: float
    monthly_cost: float
    resource_label: str
