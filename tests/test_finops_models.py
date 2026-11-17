from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db.base import Base
from backend.models.auth import User
from backend.models.finops import Resource, Scan, ScanResourceSnapshot


ROOT = Path(__file__).resolve().parents[1]
PHASE2_TABLES = {
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
}


class MultiUserSchemaTests(unittest.TestCase):
    def test_model_metadata_contains_phase_two_tables(self):
        self.assertTrue(PHASE2_TABLES.issubset(Base.metadata.tables))
        for name in PHASE2_TABLES:
            self.assertIn("user_id", Base.metadata.tables[name].columns)

    def test_composite_foreign_keys_reject_cross_user_snapshots(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            engine = create_engine(f"sqlite:///{Path(temp_dir) / 'models.sqlite3'}")

            @event.listens_for(engine, "connect")
            def enable_sqlite_foreign_keys(connection, _record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

            Base.metadata.create_all(engine)
            try:
                with Session(engine) as session:
                    first = User(full_name="First", username="first", email="first@example.test", password_hash="hash")
                    second = User(full_name="Second", username="second", email="second@example.test", password_hash="hash")
                    session.add_all([first, second])
                    session.flush()

                    scan = Scan(scan_id="scan-first", user_id=first.id, mode="synthetic", status="completed", progress=100)
                    foreign_resource = Resource(
                        user_id=second.id,
                        provider="synthetic",
                        account_id="synthetic",
                        region="unknown",
                        external_id="resource-second",
                        resource_type="instance",
                    )
                    session.add_all([scan, foreign_resource])
                    session.flush()

                    session.add(
                        ScanResourceSnapshot(
                            user_id=first.id,
                            scan_id=scan.scan_id,
                            resource_id=foreign_resource.resource_id,
                            attributes={},
                        )
                    )
                    with self.assertRaises(IntegrityError):
                        session.flush()
                    session.rollback()
            finally:
                Base.metadata.drop_all(engine)
                engine.dispose()

    def test_alembic_upgrade_downgrade_and_reupgrade_on_disposable_sqlite(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            db_path = Path(temp_dir) / "migration.sqlite3"
            config = Config(str(ROOT / "alembic.ini"))
            with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}):
                command.upgrade(config, "head")
                engine = create_engine(f"sqlite:///{db_path.as_posix()}")
                try:
                    inspector = inspect(engine)
                    tables = set(inspector.get_table_names())
                    self.assertTrue(PHASE2_TABLES.issubset(tables))
                    self.assertTrue({"users", "user_sessions", "alembic_version"}.issubset(tables))
                    foreign_keys = inspector.get_foreign_keys("scan_resource_snapshots")
                    self.assertTrue(any(fk["name"] == "fk_snapshots_scan_owner" for fk in foreign_keys))
                    self.assertTrue(any(fk["name"] == "fk_snapshots_resource_owner" for fk in foreign_keys))
                finally:
                    engine.dispose()

                command.downgrade(config, "0001_auth_users_sessions")
                engine = create_engine(f"sqlite:///{db_path.as_posix()}")
                try:
                    tables = set(inspect(engine).get_table_names())
                    self.assertTrue(PHASE2_TABLES.isdisjoint(tables))
                    self.assertTrue({"users", "user_sessions"}.issubset(tables))
                finally:
                    engine.dispose()

                command.upgrade(config, "head")
                engine = create_engine(f"sqlite:///{db_path.as_posix()}")
                try:
                    self.assertTrue(PHASE2_TABLES.issubset(inspect(engine).get_table_names()))
                finally:
                    engine.dispose()


if __name__ == "__main__":
    unittest.main()
