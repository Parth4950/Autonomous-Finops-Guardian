"""User-owned FinOps scan and workflow persistence models.

These tables are additive foundations. Existing file-backed pipeline services
continue to use their legacy paths until a later phase migrates those APIs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AWSAccount(Base):
    """User-owned AWS account connection with AES-GCM encrypted credentials."""

    __tablename__ = "aws_accounts"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_aws_accounts_id_user"),
        UniqueConstraint("user_id", "display_name", name="uq_aws_accounts_user_display_name"),
        CheckConstraint("length(trim(display_name)) > 0", name="ck_aws_accounts_display_name_nonempty"),
        CheckConstraint("length(trim(default_region)) > 0", name="ck_aws_accounts_region_nonempty"),
        CheckConstraint(
            "length(trim(access_key_id_masked)) >= 8 AND access_key_id_masked LIKE '%*%'",
            name="ck_aws_accounts_masked_key",
        ),
        CheckConstraint(
            "encrypted_credentials LIKE 'v1.%'",
            name="ck_aws_accounts_encrypted_prefix",
        ),
        CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'invalid', 'expired')",
            name="ck_aws_accounts_verification_status",
        ),
        CheckConstraint(
            "aws_account_id IS NULL OR length(aws_account_id) = 12",
            name="ck_aws_accounts_aws_account_id_len",
        ),
        Index("ix_aws_accounts_user_status", "user_id", "verification_status"),
        Index("ix_aws_accounts_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    aws_account_id: Mapped[str | None] = mapped_column(String(12))
    arn: Mapped[str | None] = mapped_column(String(512))
    default_region: Mapped[str] = mapped_column(String(64), nullable=False, default="ap-south-1")
    access_key_id_masked: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    has_session_token: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unverified")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"AWSAccount(id={self.id!r}, user_id={self.user_id!r}, "
            f"display_name={self.display_name!r}, aws_account_id={self.aws_account_id!r}, "
            f"default_region={self.default_region!r}, access_key_id_masked={self.access_key_id_masked!r}, "
            f"has_session_token={self.has_session_token!r}, verification_status={self.verification_status!r})"
        )

    def set_credentials(
        self,
        *,
        access_key_id: str,
        secret_access_key: str,
        session_token: str | None = None,
    ) -> None:
        """Mask access_key_id and encrypt secrets bound to this account's user_id."""
        from backend.utils.credential_encryption import encrypt_aws_credentials, mask_access_key_id

        if not self.user_id or self.user_id <= 0:
            raise ValueError("user_id must be set before encrypting AWS credentials.")
        cleaned_token = session_token.strip() if isinstance(session_token, str) and session_token.strip() else None
        self.access_key_id_masked = mask_access_key_id(access_key_id)
        self.encrypted_credentials = encrypt_aws_credentials(
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            session_token=cleaned_token,
            user_id=self.user_id,
        )
        self.has_session_token = cleaned_token is not None

    def decrypt_credentials(self, *, requesting_user_id: int | None = None):
        """Decrypt credentials after verifying user ownership."""
        from backend.utils.credential_encryption import CredentialTamperError, decrypt_aws_credentials

        expected_user_id = self.user_id if requesting_user_id is None else requesting_user_id
        if expected_user_id != self.user_id:
            raise CredentialTamperError("Cannot decrypt AWS credentials for a different user.")
        return decrypt_aws_credentials(self.encrypted_credentials, user_id=expected_user_id)

    def to_masked_dict(self) -> dict[str, Any]:
        """Serialize account metadata with masked key ID and no secret material."""
        from backend.utils.credential_encryption import serialize_aws_account

        return serialize_aws_account(self)


class Scan(Base):
    """One user-owned run of the existing FinOps pipeline."""

    __tablename__ = "scans"
    __table_args__ = (
        UniqueConstraint("scan_id", "user_id", name="uq_scans_scan_user"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_scans_progress_range"),
        CheckConstraint("mode IN ('synthetic', 'aws')", name="ck_scans_mode"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_scans_status",
        ),
        Index("ix_scans_user_status", "user_id", "status"),
        Index("ix_scans_user_created", "user_id", "created_at"),
    )

    scan_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="synthetic")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    current_stage: Mapped[str | None] = mapped_column(String(120))
    message: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ScanStage(Base):
    """Persisted status for an individual step in a scan."""

    __tablename__ = "scan_stages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scan_id", "user_id"],
            ["scans.scan_id", "scans.user_id"],
            ondelete="CASCADE",
            name="fk_scan_stages_scan_owner",
        ),
        UniqueConstraint("scan_id", "stage_order", name="uq_scan_stages_order"),
        CheckConstraint("stage_order > 0", name="ck_scan_stages_order_positive"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'skipped')",
            name="ck_scan_stages_status",
        ),
        Index("ix_scan_stages_user_scan", "user_id", "scan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    stage_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class Resource(Base):
    """Stable resource identity scoped to one user and provider account."""

    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("resource_id", "user_id", name="uq_resources_id_user"),
        UniqueConstraint(
            "user_id", "provider", "account_id", "region", "external_id",
            name="uq_resources_owner_identity",
        ),
        Index("ix_resources_user_type", "user_id", "resource_type"),
    )

    resource_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False, default="aws")
    account_id: Mapped[str] = mapped_column(String(128), nullable=False, default="synthetic")
    region: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ScanResourceSnapshot(Base):
    """Immutable per-scan observation of a user's resource."""

    __tablename__ = "scan_resource_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"],
            ondelete="CASCADE", name="fk_snapshots_scan_owner",
        ),
        ForeignKeyConstraint(
            ["resource_id", "user_id"], ["resources.resource_id", "resources.user_id"],
            ondelete="CASCADE", name="fk_snapshots_resource_owner",
        ),
        UniqueConstraint("snapshot_id", "user_id", "scan_id", name="uq_snapshots_id_owner_scan"),
        UniqueConstraint("scan_id", "resource_id", name="uq_snapshots_scan_resource"),
        Index("ix_snapshots_user_scan", "user_id", "scan_id"),
        Index("ix_snapshots_user_resource", "user_id", "resource_id"),
    )

    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    resource_id: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    estimated_monthly_cost: Mapped[float | None] = mapped_column(Numeric(14, 2))
    avg_cpu: Mapped[float | None] = mapped_column(Float)
    avg_network_in: Mapped[float | None] = mapped_column(Float)
    avg_network_out: Mapped[float | None] = mapped_column(Float)
    resource_label: Mapped[str | None] = mapped_column(String(64))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class Anomaly(Base):
    """Isolation Forest output associated with one scan snapshot."""

    __tablename__ = "anomalies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["snapshot_id", "user_id", "scan_id"],
            ["scan_resource_snapshots.snapshot_id", "scan_resource_snapshots.user_id", "scan_resource_snapshots.scan_id"],
            ondelete="CASCADE", name="fk_anomalies_snapshot_owner_scan",
        ),
        UniqueConstraint("scan_id", "snapshot_id", name="uq_anomalies_scan_snapshot"),
        Index("ix_anomalies_user_scan", "user_id", "scan_id"),
        Index("ix_anomalies_user_label", "user_id", "prediction_label"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    prediction: Mapped[int | None] = mapped_column(Integer)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    prediction_label: Mapped[str | None] = mapped_column(String(32))
    result_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Forecast(Base):
    """Per-resource forecast summary and time-series data for a scan."""

    __tablename__ = "forecasts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["snapshot_id", "user_id", "scan_id"],
            ["scan_resource_snapshots.snapshot_id", "scan_resource_snapshots.user_id", "scan_resource_snapshots.scan_id"],
            ondelete="CASCADE", name="fk_forecasts_snapshot_owner_scan",
        ),
        UniqueConstraint("scan_id", "snapshot_id", name="uq_forecasts_scan_snapshot"),
        Index("ix_forecasts_user_scan", "user_id", "scan_id"),
        Index("ix_forecasts_user_category", "user_id", "utilization_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    utilization_category: Mapped[str | None] = mapped_column(String(32))
    waste_probability: Mapped[str | None] = mapped_column(String(24))
    summary_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    series_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class FinOpsReport(Base):
    """Structured audit or executive report generated by a scan."""

    __tablename__ = "finops_reports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"],
            ondelete="CASCADE", name="fk_reports_scan_owner",
        ),
        UniqueConstraint("scan_id", "report_type", name="uq_reports_scan_type"),
        Index("ix_reports_user_scan", "user_id", "scan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    report_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source: Mapped[str | None] = mapped_column(String(64))
    report_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Approval(Base):
    """User-owned human approval package and current decision state."""

    __tablename__ = "approvals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"],
            ondelete="CASCADE", name="fk_approvals_scan_owner",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "user_id", "scan_id"],
            ["scan_resource_snapshots.snapshot_id", "scan_resource_snapshots.user_id", "scan_resource_snapshots.scan_id"],
            ondelete="CASCADE", name="fk_approvals_snapshot_owner_scan",
        ),
        UniqueConstraint("approval_id", "user_id", "scan_id", name="uq_approvals_id_owner_scan"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'executed')",
            name="ck_approvals_status",
        ),
        Index("ix_approvals_user_status", "user_id", "status"),
        Index("ix_approvals_user_scan", "user_id", "scan_id"),
    )

    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    risk_level: Mapped[str | None] = mapped_column(String(24))
    estimated_savings: Mapped[float | None] = mapped_column(Numeric(14, 2))
    business_justification: Mapped[str | None] = mapped_column(Text)
    execution_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now())


class ApprovalEvent(Base):
    """Append-only audit event for an approval transition."""

    __tablename__ = "approval_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"],
            ondelete="CASCADE", name="fk_approval_events_scan_owner",
        ),
        ForeignKeyConstraint(
            ["approval_id", "user_id", "scan_id"],
            ["approvals.approval_id", "approvals.user_id", "approvals.scan_id"],
            ondelete="CASCADE", name="fk_approval_events_approval_owner_scan",
        ),
        Index("ix_approval_events_user_approval", "user_id", "approval_id"),
        Index("ix_approval_events_user_scan", "user_id", "scan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approval_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    previous_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())


class Execution(Base):
    """User-owned execution result for an approved remediation package."""

    __tablename__ = "executions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"],
            ondelete="CASCADE", name="fk_executions_scan_owner",
        ),
        ForeignKeyConstraint(
            ["approval_id", "user_id", "scan_id"],
            ["approvals.approval_id", "approvals.user_id", "approvals.scan_id"],
            ondelete="CASCADE", name="fk_executions_approval_owner_scan",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "user_id", "scan_id"],
            ["scan_resource_snapshots.snapshot_id", "scan_resource_snapshots.user_id", "scan_resource_snapshots.scan_id"],
            ondelete="CASCADE", name="fk_executions_snapshot_owner_scan",
        ),
        UniqueConstraint("approval_id", name="uq_executions_approval"),
        CheckConstraint(
            "status IN ('success', 'failed', 'rolled_back', 'running')",
            name="ck_executions_status",
        ),
        CheckConstraint("mode IN ('simulation', 'real')", name="ck_executions_mode"),
        Index("ix_executions_user_scan", "user_id", "scan_id"),
        Index("ix_executions_user_status", "user_id", "status"),
    )

    execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approval_id: Mapped[str] = mapped_column(String(36), nullable=False)
    snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="simulation")
    result_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    log_lines: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    rollback_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
