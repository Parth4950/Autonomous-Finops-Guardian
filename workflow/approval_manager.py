"""
Human Approval Workflow — governance layer before cloud remediation execution.

Loads planner approval packages, queues actionable requests, and tracks
human approve/reject decisions with full audit history.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from workflow.approval_queue import ApprovalNotFoundError, ApprovalQueue, ApprovalQueueError
from workflow.models import (
    ACTIONS_REQUIRING_APPROVAL,
    ApprovalHistoryEvent,
    ApprovalPackage,
    ApprovalRecord,
    ApprovalStatus,
    ApprovalSummary,
    format_timestamp,
    utc_now,
)

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = MODULE_DIR / "results"
DEFAULT_HISTORY_DIR = MODULE_DIR / "history"
DEFAULT_PLANNER_PACKAGES_PATH = (
    _PROJECT_ROOT / "agents" / "planner" / "results" / "approval_packages.json"
)


class ApprovalWorkflowError(Exception):
    """Base exception for approval workflow operations."""


class InvalidApprovalTransitionError(ApprovalWorkflowError):
    """Raised when an approval status transition is not allowed."""


class DuplicatePendingApprovalError(ApprovalWorkflowError):
    """Raised when a resource already has a pending approval request."""


class ApprovalManager:
    """
    Enterprise human-in-the-loop approval manager.

    Queues remediation plans from the Planner Agent and governs
    approve/reject decisions before execution.
    """

    VALID_TRANSITIONS: dict[ApprovalStatus, set[ApprovalStatus]] = {
        "pending": {"approved", "rejected"},
        "approved": {"executed"},
        "rejected": set(),
        "executed": set(),
    }

    def __init__(
        self,
        queue: ApprovalQueue | None = None,
        default_reviewer: str = "finops-admin",
    ) -> None:
        self._queue = queue or ApprovalQueue(
            results_dir=DEFAULT_RESULTS_DIR,
            history_dir=DEFAULT_HISTORY_DIR,
        )
        self._default_reviewer = default_reviewer

    @property
    def queue(self) -> ApprovalQueue:
        return self._queue

    def add_approval_request(
        self,
        package: ApprovalPackage,
        *,
        approval_id: str | None = None,
        allow_duplicate_resource: bool = False,
    ) -> ApprovalRecord:
        """
        Add a new approval request from a planner package.

        Args:
            package: Planner approval package.
            approval_id: Optional explicit approval ID.
            allow_duplicate_resource: Allow multiple pending requests per resource.

        Returns:
            Created pending ApprovalRecord.

        Raises:
            DuplicatePendingApprovalError: When a pending request already exists.
            ApprovalWorkflowError: When the package does not require approval.
        """
        if not package.requires_approval:
            raise ApprovalWorkflowError(
                f"Action '{package.action}' for {package.resource_id} does not require approval."
            )

        if (
            not allow_duplicate_resource
            and package.resource_id in self._queue.pending_resource_ids()
        ):
            raise DuplicatePendingApprovalError(
                f"Resource {package.resource_id} already has a pending approval request."
            )

        record = ApprovalRecord.from_package(
            package,
            approval_id=approval_id or str(uuid.uuid4()),
        )
        self._queue.upsert_record(record)
        self._record_history_event(
            record=record,
            previous_status=None,
            new_status="pending",
            actor="planner-agent",
            notes="Approval request created from planner package.",
        )
        logger.info(
            "Created approval request %s for %s (%s)",
            record.approval_id,
            record.resource_id,
            record.action,
        )
        return record

    def ingest_planner_packages(
        self,
        packages_path: Path = DEFAULT_PLANNER_PACKAGES_PATH,
        *,
        skip_existing_pending: bool = True,
    ) -> list[ApprovalRecord]:
        """
        Load approval packages from the Planner Agent and queue actionable items.

        Args:
            packages_path: Path to approval_packages.json.
            skip_existing_pending: Skip resources that already have pending requests.

        Returns:
            List of newly created approval records.
        """
        if not packages_path.exists():
            raise FileNotFoundError(
                f"Planner approval packages not found at {packages_path}. "
                "Run agents/planner/planner.py first."
            )

        with open(packages_path, encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, list):
            raise ApprovalWorkflowError("Planner approval packages must be a JSON list.")

        created: list[ApprovalRecord] = []
        skipped_ignore = 0
        skipped_duplicate = 0

        for item in payload:
            package = ApprovalPackage.from_dict(item)
            if not package.requires_approval:
                skipped_ignore += 1
                continue

            try:
                created.append(
                    self.add_approval_request(
                        package,
                        allow_duplicate_resource=not skip_existing_pending,
                    )
                )
            except DuplicatePendingApprovalError:
                skipped_duplicate += 1
                logger.debug(
                    "Skipped duplicate pending approval for %s",
                    package.resource_id,
                )

        logger.info(
            "Ingested planner packages — created=%d, skipped_ignore=%d, skipped_duplicate=%d",
            len(created),
            skipped_ignore,
            skipped_duplicate,
        )
        return created

    def list_pending_approvals(self) -> list[ApprovalRecord]:
        """Return all pending approval requests."""
        return [
            record
            for record in self._queue.load_records()
            if record.status == "pending"
        ]

    def list_approved(self) -> list[ApprovalRecord]:
        """Return all approved requests awaiting execution."""
        return [
            record
            for record in self._queue.load_records()
            if record.status == "approved"
        ]

    def list_rejected(self) -> list[ApprovalRecord]:
        """Return all rejected approval requests."""
        return [
            record
            for record in self._queue.load_records()
            if record.status == "rejected"
        ]

    def list_executed(self) -> list[ApprovalRecord]:
        """Return all executed approval requests."""
        return [
            record
            for record in self._queue.load_records()
            if record.status == "executed"
        ]

    def approve_request(
        self,
        approval_id: str,
        *,
        reviewer: str | None = None,
        notes: str | None = None,
    ) -> ApprovalRecord:
        """Approve a pending remediation request."""
        return self._transition(
            approval_id=approval_id,
            target_status="approved",
            actor=reviewer or self._default_reviewer,
            notes=notes or "Approved for remediation execution.",
        )

    def reject_request(
        self,
        approval_id: str,
        *,
        reviewer: str | None = None,
        notes: str | None = None,
    ) -> ApprovalRecord:
        """Reject a pending remediation request."""
        return self._transition(
            approval_id=approval_id,
            target_status="rejected",
            actor=reviewer or self._default_reviewer,
            notes=notes or "Rejected by reviewer.",
        )

    def mark_executed(
        self,
        approval_id: str,
        *,
        actor: str = "executor-agent",
        notes: str | None = None,
    ) -> ApprovalRecord:
        """Mark an approved request as executed (Executor integration hook)."""
        return self._transition(
            approval_id=approval_id,
            target_status="executed",
            actor=actor,
            notes=notes or "Remediation executed successfully.",
        )

    def get_request(self, approval_id: str) -> ApprovalRecord:
        """Return a single approval request."""
        return self._queue.get_record(approval_id)

    def view_history(
        self,
        approval_id: str | None = None,
    ) -> list[ApprovalHistoryEvent]:
        """
        View approval audit history.

        Args:
            approval_id: Optional filter for a specific approval request.

        Returns:
            Chronological list of history events.
        """
        if approval_id:
            return self._queue.history_for_approval(approval_id)
        return self._queue.load_history()

    def summarize(self) -> ApprovalSummary:
        """Compute aggregate approval workflow metrics."""
        records = self._queue.load_records()
        pending = [record for record in records if record.status == "pending"]
        approved = [record for record in records if record.status == "approved"]
        rejected = [record for record in records if record.status == "rejected"]
        executed = [record for record in records if record.status == "executed"]

        return ApprovalSummary(
            total_requests=len(records),
            pending=len(pending),
            approved=len(approved),
            rejected=len(rejected),
            executed=len(executed),
            pending_savings=sum(record.estimated_savings for record in pending),
            approved_savings=sum(record.estimated_savings for record in approved),
        )

    def _transition(
        self,
        approval_id: str,
        target_status: ApprovalStatus,
        actor: str,
        notes: str | None,
    ) -> ApprovalRecord:
        record = self._queue.get_record(approval_id)
        allowed = self.VALID_TRANSITIONS.get(record.status, set())

        if target_status not in allowed:
            raise InvalidApprovalTransitionError(
                f"Cannot transition approval {approval_id} from "
                f"'{record.status}' to '{target_status}'."
            )

        previous_status = record.status
        record.status = target_status
        record.updated_at = utc_now()
        record.reviewed_by = actor
        record.review_notes = notes
        self._queue.upsert_record(record)
        self._record_history_event(
            record=record,
            previous_status=previous_status,
            new_status=target_status,
            actor=actor,
            notes=notes,
        )
        logger.info(
            "Approval %s transitioned %s -> %s by %s",
            approval_id,
            previous_status,
            target_status,
            actor,
        )
        return record

    def _record_history_event(
        self,
        record: ApprovalRecord,
        previous_status: ApprovalStatus | None,
        new_status: ApprovalStatus,
        actor: str,
        notes: str | None,
    ) -> None:
        event = ApprovalHistoryEvent(
            approval_id=record.approval_id,
            resource_id=record.resource_id,
            previous_status=previous_status,
            new_status=new_status,
            timestamp=utc_now(),
            actor=actor,
            notes=notes,
        )
        self._queue.append_history_event(event)


class ApprovalReporter:
    """Print human-readable approval workflow reports."""

    @staticmethod
    def _print_records(title: str, records: list[ApprovalRecord]) -> None:
        print(f"=== {title} ===\n")
        if not records:
            print("None.")
            print()
            return

        rows = [
            {
                "approval_id": record.approval_id[:8] + "...",
                "resource_id": record.resource_id,
                "action": record.action,
                "risk_level": record.risk_level,
                "estimated_savings": record.estimated_savings,
                "status": record.status,
                "timestamp": format_timestamp(record.updated_at),
            }
            for record in records
        ]
        print(pd.DataFrame(rows).to_string(index=False))
        print()

    @classmethod
    def print_reports(cls, manager: ApprovalManager) -> None:
        """Print all required approval workflow reports."""
        summary = manager.summarize()

        print("\n=== APPROVAL WORKFLOW SUMMARY ===\n")
        print(f"Total Requests                 : {summary.total_requests}")
        print(f"Pending                        : {summary.pending}")
        print(f"Approved                       : {summary.approved}")
        print(f"Rejected                       : {summary.rejected}")
        print(f"Executed                       : {summary.executed}")
        print()
        print(
            "Potential Savings Awaiting Approval: "
            f"${summary.pending_savings:,.2f}"
        )
        print(f"Approved Savings (Ready to Execute): ${summary.approved_savings:,.2f}")
        print()

        cls._print_records("PENDING ACTIONS", manager.list_pending_approvals())
        cls._print_records("APPROVED ACTIONS", manager.list_approved())
        cls._print_records("REJECTED ACTIONS", manager.list_rejected())

        print("=== POTENTIAL SAVINGS AWAITING APPROVAL ===\n")
        pending = manager.list_pending_approvals()
        if not pending:
            print("$0.00 — no pending remediation actions.")
        else:
            by_action = (
                pd.DataFrame(
                    [
                        {
                            "action": record.action,
                            "estimated_savings": record.estimated_savings,
                        }
                        for record in pending
                    ]
                )
                .groupby("action", as_index=False)["estimated_savings"]
                .sum()
                .sort_values("estimated_savings", ascending=False)
            )
            total = float(by_action["estimated_savings"].sum())
            print(by_action.to_string(index=False))
            print()
            print(f"Total Pending Savings: ${total:,.2f}")
        print()


class ApprovalWorkflowPipeline:
    """End-to-end approval workflow demonstration."""

    def __init__(
        self,
        manager: ApprovalManager | None = None,
        packages_path: Path = DEFAULT_PLANNER_PACKAGES_PATH,
    ) -> None:
        self._manager = manager or ApprovalManager()
        self._packages_path = packages_path

    def run(self, *, simulate_reviews: bool = True) -> ApprovalSummary:
        """
        Execute the approval workflow pipeline.

        Args:
            simulate_reviews: When True, auto-approve low-risk terminate actions
                and reject one medium-risk item to demonstrate governance flow.

        Returns:
            Final approval summary metrics.
        """
        created = self._manager.ingest_planner_packages(self._packages_path)
        logger.info("Queued %d new approval request(s)", len(created))

        if simulate_reviews and created:
            self._simulate_reviews(created)

        ApprovalReporter.print_reports(self._manager)

        print("=== OUTPUT FILES ===\n")
        print(f"Approvals CSV  : {self._manager.queue.csv_path}")
        print(f"Approvals JSON : {self._manager.queue.json_path}")
        print(f"History JSON   : {self._manager.queue.history_path}")
        print()

        return self._manager.summarize()

    def _simulate_reviews(self, created: list[ApprovalRecord]) -> None:
        """
        Demonstrate approve/reject transitions for portfolio review.

        Approves the top 5 low-risk terminate requests and rejects one
        medium-risk manual_review request to show governance controls.
        """
        terminate_candidates = sorted(
            [
                record
                for record in created
                if record.action == "terminate" and record.risk_level == "low"
            ],
            key=lambda record: record.estimated_savings,
            reverse=True,
        )
        for record in terminate_candidates[:5]:
            self._manager.approve_request(
                record.approval_id,
                reviewer="cloud-engineer",
                notes="Low-risk zombie resource approved for termination.",
            )

        manual_candidates = [
            record
            for record in created
            if record.action == "manual_review" and record.risk_level == "medium"
        ]
        if manual_candidates:
            reject_target = manual_candidates[0]
            self._manager.reject_request(
                reject_target.approval_id,
                reviewer="platform-lead",
                notes="Requires additional dependency validation before action.",
            )


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """Run the Human Approval Workflow pipeline."""
    _configure_logging()

    try:
        ApprovalWorkflowPipeline().run()
        return 0
    except (ApprovalQueueError, ApprovalWorkflowError, FileNotFoundError) as exc:
        logger.error("Workflow error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Approval workflow failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
