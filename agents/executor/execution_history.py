"""Execution history persistence for the Executor Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)

ExecutionStatus = Literal["success", "failed", "rolled_back"]


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def format_timestamp(value: datetime) -> str:
    """Format a datetime as an ISO-8601 UTC string."""
    return value.astimezone(timezone.utc).isoformat()


@dataclass
class ExecutionRecord:
    """Persisted remediation execution record."""

    execution_id: str
    approval_id: str
    resource_id: str
    action: str
    status: ExecutionStatus
    timestamp: datetime
    mode: str
    log_path: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Convert to a dictionary for JSON export."""
        return {
            "execution_id": self.execution_id,
            "approval_id": self.approval_id,
            "resource_id": self.resource_id,
            "action": self.action,
            "status": self.status,
            "timestamp": format_timestamp(self.timestamp),
            "mode": self.mode,
            "log_path": self.log_path,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str | None]) -> ExecutionRecord:
        """Build an execution record from persisted storage."""
        return cls(
            execution_id=str(payload["execution_id"]),
            approval_id=str(payload["approval_id"]),
            resource_id=str(payload["resource_id"]),
            action=str(payload["action"]),
            status=payload["status"],  # type: ignore[arg-type]
            timestamp=datetime.fromisoformat(str(payload["timestamp"])),
            mode=str(payload.get("mode", "simulation")),
            log_path=payload.get("log_path"),
            error_message=payload.get("error_message"),
        )

    def to_csv_row(self) -> dict[str, str | None]:
        """Return CSV export columns for this record."""
        return {
            "execution_id": self.execution_id,
            "approval_id": self.approval_id,
            "resource_id": self.resource_id,
            "action": self.action,
            "status": self.status,
            "timestamp": format_timestamp(self.timestamp),
        }


class ExecutionHistoryStore:
    """File-backed store for remediation execution history."""

    EXPORT_COLUMNS = [
        "execution_id",
        "approval_id",
        "resource_id",
        "action",
        "status",
        "timestamp",
    ]

    def __init__(self, results_dir: Path, csv_path: Path | None = None) -> None:
        self._results_dir = results_dir
        self._csv_path = csv_path or results_dir / "execution_history.csv"
        self._results_dir.mkdir(parents=True, exist_ok=True)

    @property
    def csv_path(self) -> Path:
        return self._csv_path

    def load_records(self) -> list[ExecutionRecord]:
        """Load execution records from CSV storage."""
        if not self._csv_path.exists():
            return []

        dataframe = pd.read_csv(self._csv_path)
        records: list[ExecutionRecord] = []

        for _, row in dataframe.iterrows():
            records.append(
                ExecutionRecord(
                    execution_id=str(row["execution_id"]),
                    approval_id=str(row["approval_id"]),
                    resource_id=str(row["resource_id"]),
                    action=str(row["action"]),
                    status=row["status"],  # type: ignore[arg-type]
                    timestamp=datetime.fromisoformat(str(row["timestamp"])),
                    mode=str(row.get("mode", "simulation"))
                    if "mode" in dataframe.columns
                    else "simulation",
                )
            )

        return records

    def append_record(self, record: ExecutionRecord) -> None:
        """Append a single execution record to history."""
        records = self.load_records()
        records.append(record)
        self.save_records(records)

    def save_records(self, records: list[ExecutionRecord]) -> None:
        """Persist all execution records to CSV."""
        sorted_records = sorted(records, key=lambda item: item.timestamp)
        rows = [record.to_csv_row() for record in sorted_records]
        dataframe = pd.DataFrame(rows, columns=self.EXPORT_COLUMNS)
        dataframe.to_csv(self._csv_path, index=False)
        logger.info("Saved %d execution record(s) to %s", len(sorted_records), self._csv_path)

    def get_by_approval_id(self, approval_id: str) -> ExecutionRecord | None:
        """Return an execution record for a given approval ID."""
        for record in self.load_records():
            if record.approval_id == approval_id:
                return record
        return None
