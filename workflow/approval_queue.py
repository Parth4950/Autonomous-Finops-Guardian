"""Persistent approval queue for human-in-the-loop governance."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from workflow.models import ApprovalHistoryEvent, ApprovalRecord, format_timestamp

logger = logging.getLogger(__name__)


class ApprovalQueueError(Exception):
    """Base exception for approval queue operations."""


class ApprovalNotFoundError(ApprovalQueueError):
    """Raised when an approval ID does not exist."""


class ApprovalQueue:
    """
    File-backed approval queue.

    Persists active approvals to CSV/JSON and maintains an append-only
    audit history for governance traceability.
    """

    EXPORT_COLUMNS = ["approval_id", "resource_id", "action", "status", "timestamp"]

    def __init__(
        self,
        results_dir: Path,
        history_dir: Path,
        csv_path: Path | None = None,
        json_path: Path | None = None,
        history_path: Path | None = None,
    ) -> None:
        self._results_dir = results_dir
        self._history_dir = history_dir
        self._csv_path = csv_path or results_dir / "approvals.csv"
        self._json_path = json_path or results_dir / "approvals.json"
        self._history_path = history_path or history_dir / "approval_history.json"

        self._results_dir.mkdir(parents=True, exist_ok=True)
        self._history_dir.mkdir(parents=True, exist_ok=True)

        if not self._history_path.exists():
            self._write_history([])

    @property
    def csv_path(self) -> Path:
        return self._csv_path

    @property
    def json_path(self) -> Path:
        return self._json_path

    @property
    def history_path(self) -> Path:
        return self._history_path

    def load_records(self) -> list[ApprovalRecord]:
        """Load all approval records from JSON storage."""
        if not self._json_path.exists():
            return []

        with open(self._json_path, encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, list):
            raise ApprovalQueueError(f"Invalid approvals JSON format: {self._json_path}")

        return [ApprovalRecord.from_dict(item) for item in payload]

    def save_records(self, records: list[ApprovalRecord]) -> None:
        """Persist approval records to CSV and JSON."""
        sorted_records = sorted(records, key=lambda record: record.created_at)

        with open(self._json_path, "w", encoding="utf-8") as handle:
            json.dump(
                [record.to_dict() for record in sorted_records],
                handle,
                indent=2,
            )

        export_rows = [record.to_export_row() for record in sorted_records]
        dataframe = pd.DataFrame(export_rows, columns=self.EXPORT_COLUMNS)
        dataframe.to_csv(self._csv_path, index=False)

        logger.info(
            "Saved %d approval record(s) to %s and %s",
            len(sorted_records),
            self._csv_path,
            self._json_path,
        )

    def get_record(self, approval_id: str) -> ApprovalRecord:
        """Return a single approval record by ID."""
        for record in self.load_records():
            if record.approval_id == approval_id:
                return record
        raise ApprovalNotFoundError(f"Approval not found: {approval_id}")

    def upsert_record(self, record: ApprovalRecord) -> None:
        """Insert or update a single approval record."""
        records = self.load_records()
        updated = False

        for index, existing in enumerate(records):
            if existing.approval_id == record.approval_id:
                records[index] = record
                updated = True
                break

        if not updated:
            records.append(record)

        self.save_records(records)

    def append_records(self, new_records: list[ApprovalRecord]) -> int:
        """Append new records, skipping duplicate approval IDs."""
        records = self.load_records()
        existing_ids = {record.approval_id for record in records}
        appended = [record for record in new_records if record.approval_id not in existing_ids]

        if appended:
            records.extend(appended)
            self.save_records(records)

        return len(appended)

    def load_history(self) -> list[ApprovalHistoryEvent]:
        """Load the full approval audit history."""
        with open(self._history_path, encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, list):
            raise ApprovalQueueError(f"Invalid history JSON format: {self._history_path}")

        return [ApprovalHistoryEvent.from_dict(item) for item in payload]

    def append_history_event(self, event: ApprovalHistoryEvent) -> None:
        """Append a governance audit event to history."""
        history = self.load_history()
        history.append(event)
        self._write_history(history)
        logger.info(
            "Recorded approval history event: %s -> %s for %s",
            event.previous_status,
            event.new_status,
            event.approval_id,
        )

    def _write_history(self, events: list[ApprovalHistoryEvent]) -> None:
        with open(self._history_path, "w", encoding="utf-8") as handle:
            json.dump([event.to_dict() for event in events], handle, indent=2)

    def history_for_approval(self, approval_id: str) -> list[ApprovalHistoryEvent]:
        """Return audit events for a specific approval request."""
        return [
            event
            for event in self.load_history()
            if event.approval_id == approval_id
        ]

    def pending_resource_ids(self) -> set[str]:
        """Return resource IDs that already have pending approvals."""
        return {
            record.resource_id
            for record in self.load_records()
            if record.status == "pending"
        }
