"""Idempotent startup database migration runner for PostgreSQL and SQLite."""

from __future__ import annotations

import logging
from pathlib import Path
import threading

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI_PATH = _PROJECT_ROOT / "alembic.ini"
_MIGRATION_LOCK = threading.Lock()

REQUIRED_TABLES: tuple[str, ...] = (
    "users",
    "user_sessions",
    "scans",
    "scan_stages",
    "resources",
    "scan_resource_snapshots",
    "anomalies",
    "forecasts",
    "finops_reports",
    "approvals",
    "approval_events",
    "executions",
    "aws_accounts",
)


def _alembic_config() -> Config:
    cfg = Config(str(_ALEMBIC_INI_PATH))
    cfg.set_main_option("script_location", str(_PROJECT_ROOT / "migrations"))
    return cfg


def run_database_migrations(engine: Engine | None = None) -> str | None:
    """
    Ensure Alembic migrations 0001 -> 0002 -> 0003 are applied to the active database
    without dropping or overwriting existing records.
    """
    if engine is None:
        from backend.db.session import get_engine

        engine = get_engine()

    with _MIGRATION_LOCK:
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        head_revision = script.get_current_head()

        with engine.connect() as connection:
            existing_tables = set(inspect(connection).get_table_names())
            migration_ctx = MigrationContext.configure(connection)
            current_revision = migration_ctx.get_current_revision()

            # Fast path: already at head and all required tables exist.
            if current_revision == head_revision and all(
                table in existing_tables for table in REQUIRED_TABLES
            ):
                return current_revision

            # Recover safely if alembic_version was stamped while core tables are missing.
            if "alembic_version" in existing_tables and "users" not in existing_tables:
                logger.warning(
                    "Detected alembic_version row (%s) without 'users' table; resetting alembic_version stamp to run migrations cleanly.",
                    current_revision,
                )
                connection.execute(text("DELETE FROM alembic_version"))
                if connection.in_transaction():
                    connection.commit()

            logger.info(
                "Applying database migrations (current=%s -> head=%s)",
                current_revision,
                head_revision,
            )
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            if connection.in_transaction():
                connection.commit()

        with engine.connect() as verify_conn:
            final_tables = set(inspect(verify_conn).get_table_names())
            final_revision = MigrationContext.configure(verify_conn).get_current_revision()

        missing = [table for table in REQUIRED_TABLES if table not in final_tables]
        if missing:
            raise RuntimeError(
                f"Database migration finished at revision {final_revision}, but required tables are missing: {', '.join(missing)}"
            )

        logger.info("Database schema verified at revision %s", final_revision)
        return final_revision
