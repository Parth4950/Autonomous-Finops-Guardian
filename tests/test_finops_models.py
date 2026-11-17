from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db.base import Base
from backend.db.migrations import REQUIRED_TABLES, run_database_migrations
from backend.db.session import ensure_database_migrated, get_engine
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

    def test_startup_migration_runner_creates_tables_preserves_data_and_recovers_missing_users_table(self):
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            db_path = Path(temp_dir) / "startup-migrate.sqlite3"
            engine = create_engine(f"sqlite:///{db_path.as_posix()}")
            try:
                rev = run_database_migrations(engine)
                self.assertEqual(rev, "0003_user_aws_accounts")
                tables = set(inspect(engine).get_table_names())
                self.assertTrue(set(REQUIRED_TABLES).issubset(tables))

                # Insert a user and re-run migrations to verify existing data is preserved
                with Session(engine) as session:
                    session.add(
                        User(
                            full_name="Preserved User",
                            username="preserved.user",
                            email="preserved@example.test",
                            password_hash="hash",
                        )
                    )
                    session.commit()

                rev_again = run_database_migrations(engine)
                self.assertEqual(rev_again, "0003_user_aws_accounts")
                with Session(engine) as session:
                    count = session.query(User).filter(User.username == "preserved.user").count()
                    self.assertEqual(count, 1)
            finally:
                engine.dispose()

            # Simulate a database where alembic_version was stamped but 'users' table is missing
            broken_db_path = Path(temp_dir) / "broken-stamp.sqlite3"
            broken_engine = create_engine(f"sqlite:///{broken_db_path.as_posix()}")
            try:
                with broken_engine.connect() as conn:
                    conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
                    conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0003_user_aws_accounts')"))
                    conn.commit()

                recovered_rev = run_database_migrations(broken_engine)
                self.assertEqual(recovered_rev, "0003_user_aws_accounts")
                recovered_tables = set(inspect(broken_engine).get_table_names())
                self.assertTrue(set(REQUIRED_TABLES).issubset(recovered_tables))
            finally:
                broken_engine.dispose()

            # Verify ensure_database_migrated() migrates the configured DATABASE_URL automatically
            fresh_url_path = Path(temp_dir) / "fresh-env-url.sqlite3"
            fresh_url = f"sqlite:///{fresh_url_path.as_posix()}"
            get_engine.cache_clear()
            try:
                with patch.dict(os.environ, {"DATABASE_URL": fresh_url}):
                    ensure_database_migrated()
                    runtime_engine = get_engine()
                    self.assertTrue(set(REQUIRED_TABLES).issubset(inspect(runtime_engine).get_table_names()))
            finally:
                get_engine().dispose()
                get_engine.cache_clear()




if __name__ == "__main__":
    unittest.main()
