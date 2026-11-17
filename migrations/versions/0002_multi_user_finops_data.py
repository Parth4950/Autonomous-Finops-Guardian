"""Add user-owned FinOps scan, result, approval, and execution tables."""

from alembic import op
import sqlalchemy as sa


revision = "0002_multi_user_finops_data"
down_revision = "0001_auth_users_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.SmallInteger(), nullable=False),
        sa.Column("current_stage", sa.String(length=120)),
        sa.Column("message", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_scans_progress_range"),
        sa.CheckConstraint("mode IN ('synthetic', 'aws')", name="ck_scans_mode"),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled')", name="ck_scans_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scan_id"),
        sa.UniqueConstraint("scan_id", "user_id", name="uq_scans_scan_user"),
    )
    op.create_index("ix_scans_user_status", "scans", ["user_id", "status"])
    op.create_index("ix_scans_user_created", "scans", ["user_id", "created_at"])

    op.create_table(
        "resources",
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("resource_id"),
        sa.UniqueConstraint("resource_id", "user_id", name="uq_resources_id_user"),
        sa.UniqueConstraint("user_id", "provider", "account_id", "region", "external_id", name="uq_resources_owner_identity"),
    )
    op.create_index("ix_resources_user_type", "resources", ["user_id", "resource_type"])

    op.create_table(
        "scan_stages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("stage_order", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.CheckConstraint("stage_order > 0", name="ck_scan_stages_order_positive"),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'skipped')", name="ck_scan_stages_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"], ondelete="CASCADE", name="fk_scan_stages_scan_owner"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "stage_order", name="uq_scan_stages_order"),
    )
    op.create_index("ix_scan_stages_user_scan", "scan_stages", ["user_id", "scan_id"])

    op.create_table(
        "scan_resource_snapshots",
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_monthly_cost", sa.Numeric(precision=14, scale=2)),
        sa.Column("avg_cpu", sa.Float()),
        sa.Column("avg_network_in", sa.Float()),
        sa.Column("avg_network_out", sa.Float()),
        sa.Column("resource_label", sa.String(length=64)),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"], ondelete="CASCADE", name="fk_snapshots_scan_owner"),
        sa.ForeignKeyConstraint(["resource_id", "user_id"], ["resources.resource_id", "resources.user_id"], ondelete="CASCADE", name="fk_snapshots_resource_owner"),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint("snapshot_id", "user_id", "scan_id", name="uq_snapshots_id_owner_scan"),
        sa.UniqueConstraint("scan_id", "resource_id", name="uq_snapshots_scan_resource"),
    )
    op.create_index("ix_snapshots_user_scan", "scan_resource_snapshots", ["user_id", "scan_id"])
    op.create_index("ix_snapshots_user_resource", "scan_resource_snapshots", ["user_id", "resource_id"])

    op.create_table(
        "anomalies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("prediction", sa.Integer()),
        sa.Column("anomaly_score", sa.Float()),
        sa.Column("prediction_label", sa.String(length=32)),
        sa.Column("result_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id", "user_id", "scan_id"], ["scan_resource_snapshots.snapshot_id", "scan_resource_snapshots.user_id", "scan_resource_snapshots.scan_id"], ondelete="CASCADE", name="fk_anomalies_snapshot_owner_scan"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "snapshot_id", name="uq_anomalies_scan_snapshot"),
    )
    op.create_index("ix_anomalies_user_scan", "anomalies", ["user_id", "scan_id"])
    op.create_index("ix_anomalies_user_label", "anomalies", ["user_id", "prediction_label"])

    op.create_table(
        "forecasts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("utilization_category", sa.String(length=32)),
        sa.Column("waste_probability", sa.String(length=24)),
        sa.Column("summary_data", sa.JSON(), nullable=False),
        sa.Column("series_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id", "user_id", "scan_id"], ["scan_resource_snapshots.snapshot_id", "scan_resource_snapshots.user_id", "scan_resource_snapshots.scan_id"], ondelete="CASCADE", name="fk_forecasts_snapshot_owner_scan"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "snapshot_id", name="uq_forecasts_scan_snapshot"),
    )
    op.create_index("ix_forecasts_user_scan", "forecasts", ["user_id", "scan_id"])
    op.create_index("ix_forecasts_user_category", "forecasts", ["user_id", "utilization_category"])

    op.create_table(
        "finops_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("report_type", sa.String(length=48), nullable=False),
        sa.Column("source", sa.String(length=64)),
        sa.Column("report_data", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"], ondelete="CASCADE", name="fk_reports_scan_owner"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "report_type", name="uq_reports_scan_type"),
    )
    op.create_index("ix_reports_user_scan", "finops_reports", ["user_id", "scan_id"])

    op.create_table(
        "approvals",
        sa.Column("approval_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(length=24)),
        sa.Column("estimated_savings", sa.Numeric(precision=14, scale=2)),
        sa.Column("business_justification", sa.Text()),
        sa.Column("execution_steps", sa.JSON(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer()),
        sa.Column("review_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'executed')", name="ck_approvals_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"], ondelete="CASCADE", name="fk_approvals_scan_owner"),
        sa.ForeignKeyConstraint(["snapshot_id", "user_id", "scan_id"], ["scan_resource_snapshots.snapshot_id", "scan_resource_snapshots.user_id", "scan_resource_snapshots.scan_id"], ondelete="CASCADE", name="fk_approvals_snapshot_owner_scan"),
        sa.PrimaryKeyConstraint("approval_id"),
        sa.UniqueConstraint("approval_id", "user_id", "scan_id", name="uq_approvals_id_owner_scan"),
    )
    op.create_index("ix_approvals_user_status", "approvals", ["user_id", "status"])
    op.create_index("ix_approvals_user_scan", "approvals", ["user_id", "scan_id"])

    op.create_table(
        "approval_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("approval_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.Integer()),
        sa.Column("previous_status", sa.String(length=20)),
        sa.Column("new_status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"], ondelete="CASCADE", name="fk_approval_events_scan_owner"),
        sa.ForeignKeyConstraint(["approval_id", "user_id", "scan_id"], ["approvals.approval_id", "approvals.user_id", "approvals.scan_id"], ondelete="CASCADE", name="fk_approval_events_approval_owner_scan"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_events_user_approval", "approval_events", ["user_id", "approval_id"])
    op.create_index("ix_approval_events_user_scan", "approval_events", ["user_id", "scan_id"])

    op.create_table(
        "executions",
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("approval_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("result_data", sa.JSON(), nullable=False),
        sa.Column("log_lines", sa.JSON(), nullable=False),
        sa.Column("rollback_steps", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('success', 'failed', 'rolled_back', 'running')", name="ck_executions_status"),
        sa.CheckConstraint("mode IN ('simulation', 'real')", name="ck_executions_mode"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_id", "user_id"], ["scans.scan_id", "scans.user_id"], ondelete="CASCADE", name="fk_executions_scan_owner"),
        sa.ForeignKeyConstraint(["approval_id", "user_id", "scan_id"], ["approvals.approval_id", "approvals.user_id", "approvals.scan_id"], ondelete="CASCADE", name="fk_executions_approval_owner_scan"),
        sa.ForeignKeyConstraint(["snapshot_id", "user_id", "scan_id"], ["scan_resource_snapshots.snapshot_id", "scan_resource_snapshots.user_id", "scan_resource_snapshots.scan_id"], ondelete="CASCADE", name="fk_executions_snapshot_owner_scan"),
        sa.PrimaryKeyConstraint("execution_id"),
        sa.UniqueConstraint("approval_id", name="uq_executions_approval"),
    )
    op.create_index("ix_executions_user_scan", "executions", ["user_id", "scan_id"])
    op.create_index("ix_executions_user_status", "executions", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_executions_user_status", table_name="executions")
    op.drop_index("ix_executions_user_scan", table_name="executions")
    op.drop_table("executions")

    op.drop_index("ix_approval_events_user_scan", table_name="approval_events")
    op.drop_index("ix_approval_events_user_approval", table_name="approval_events")
    op.drop_table("approval_events")

    op.drop_index("ix_approvals_user_scan", table_name="approvals")
    op.drop_index("ix_approvals_user_status", table_name="approvals")
    op.drop_table("approvals")

    op.drop_index("ix_reports_user_scan", table_name="finops_reports")
    op.drop_table("finops_reports")

    op.drop_index("ix_forecasts_user_category", table_name="forecasts")
    op.drop_index("ix_forecasts_user_scan", table_name="forecasts")
    op.drop_table("forecasts")

    op.drop_index("ix_anomalies_user_label", table_name="anomalies")
    op.drop_index("ix_anomalies_user_scan", table_name="anomalies")
    op.drop_table("anomalies")

    op.drop_index("ix_snapshots_user_resource", table_name="scan_resource_snapshots")
    op.drop_index("ix_snapshots_user_scan", table_name="scan_resource_snapshots")
    op.drop_table("scan_resource_snapshots")

    op.drop_index("ix_scan_stages_user_scan", table_name="scan_stages")
    op.drop_table("scan_stages")

    op.drop_index("ix_resources_user_type", table_name="resources")
    op.drop_table("resources")

    op.drop_index("ix_scans_user_created", table_name="scans")
    op.drop_index("ix_scans_user_status", table_name="scans")
    op.drop_table("scans")
