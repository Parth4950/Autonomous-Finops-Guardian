"""Add user-owned AWS account connections table with encrypted credentials."""

from alembic import op
import sqlalchemy as sa


revision = "0003_user_aws_accounts"
down_revision = "0002_multi_user_finops_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aws_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("aws_account_id", sa.String(length=12), nullable=True),
        sa.Column("arn", sa.String(length=512), nullable=True),
        sa.Column("default_region", sa.String(length=64), nullable=False),
        sa.Column("access_key_id_masked", sa.String(length=32), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("has_session_token", sa.Boolean(), nullable=False),
        sa.Column("verification_status", sa.String(length=24), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_aws_accounts_display_name_nonempty"),
        sa.CheckConstraint("length(trim(default_region)) > 0", name="ck_aws_accounts_region_nonempty"),
        sa.CheckConstraint(
            "length(trim(access_key_id_masked)) >= 8 AND access_key_id_masked LIKE '%*%'",
            name="ck_aws_accounts_masked_key",
        ),
        sa.CheckConstraint(
            "encrypted_credentials LIKE 'v1.%'",
            name="ck_aws_accounts_encrypted_prefix",
        ),
        sa.CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'invalid', 'expired')",
            name="ck_aws_accounts_verification_status",
        ),
        sa.CheckConstraint(
            "aws_account_id IS NULL OR length(aws_account_id) = 12",
            name="ck_aws_accounts_aws_account_id_len",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_aws_accounts_id_user"),
        sa.UniqueConstraint("user_id", "display_name", name="uq_aws_accounts_user_display_name"),
    )
    op.create_index("ix_aws_accounts_user_status", "aws_accounts", ["user_id", "verification_status"])
    op.create_index("ix_aws_accounts_user_created", "aws_accounts", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_aws_accounts_user_created", table_name="aws_accounts")
    op.drop_index("ix_aws_accounts_user_status", table_name="aws_accounts")
    op.drop_table("aws_accounts")
