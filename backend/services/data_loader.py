"""Shared data loading utilities for backend services."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class DataNotFoundError(FileNotFoundError):
    """Raised when an expected agent output file is missing."""


class DataLoader:
    """Load agent output files from disk."""

    @staticmethod
    def read_csv(path: Path) -> list[dict[str, Any]]:
        """Read a CSV file into a list of dictionaries."""
        if not path.exists():
            raise DataNotFoundError(f"Data file not found: {path}")

        dataframe = pd.read_csv(path)
        records = dataframe.to_dict(orient="records")
        logger.debug("Loaded %d record(s) from %s", len(records), path)
        return records

    @staticmethod
    def read_json(path: Path) -> Any:
        """Read a JSON file."""
        if not path.exists():
            raise DataNotFoundError(f"Data file not found: {path}")

        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)

        logger.debug("Loaded JSON payload from %s", path)
        return payload

    @staticmethod
    def coerce_bool(value: Any) -> bool:
        """Coerce CSV boolean-like values to bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes"}
        return bool(value)
