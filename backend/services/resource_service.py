"""Resource inventory service."""

from __future__ import annotations

from backend.models.paths import RESOURCES_CSV
from backend.schemas.resources import ResourceItem
from backend.services.data_loader import DataLoader


class ResourceService:
    """Expose cloud resource inventory derived from Scout/synthetic pipeline outputs."""

    def __init__(self, loader: DataLoader | None = None) -> None:
        self._loader = loader or DataLoader()

    def list_resources(self) -> list[ResourceItem]:
        """Return all discovered cloud resources."""
        records = self._loader.read_csv(RESOURCES_CSV)
        return [ResourceItem.model_validate(record) for record in records]
