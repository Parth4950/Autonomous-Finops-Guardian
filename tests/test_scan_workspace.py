from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.auth import User
from backend.models.finops import Scan, ScanStage
from backend.services.scan_service import ScanService


def _await_terminal(factory, scan_ids, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with factory() as db:
            states = {
                scan.scan_id: scan.status
                for scan in db.query(Scan).filter(Scan.scan_id.in_(scan_ids)).all()
            }
        if len(states) == len(scan_ids) and all(
            value in {"completed", "failed"} for value in states.values()
        ):
            return states
        time.sleep(0.02)
    raise AssertionError("scan workers did not reach a terminal state")


class ScanWorkspaceIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.engine = create_engine(
            f"sqlite:///{self.tmp_path / 'scan-tests.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.scan_db = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.scan_db() as db:
            db.add_all(
                [
                    User(
                        full_name="Scan User One",
                        username="scan-user-one",
                        email="one@example.test",
                        password_hash="not-a-real-password-hash",
                    ),
                    User(
                        full_name="Scan User Two",
                        username="scan-user-two",
                        email="two@example.test",
                        password_hash="not-a-real-password-hash",
                    ),
                ]
            )
            db.commit()

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_scan_workspaces_are_isolated_for_concurrent_users(self) -> None:
        workspace_root = self.tmp_path / "workspaces"
        barrier = threading.Barrier(2)

        def runner(command, *, env, **kwargs):
            workspace = env["FINOPS_WORKSPACE_DIR"]
            marker = workspace + "/worker-marker.txt"
            barrier.wait(timeout=5)
            Path(marker).parent.mkdir(parents=True, exist_ok=True)
            Path(marker).write_text(workspace, encoding="utf-8")
            script = command[1].replace("\\", "/")
            if script.endswith("synthetic_data/generate_resources.py"):
                root = Path(workspace)
                resources = root / "synthetic_data" / "cloud_resources.csv"
                resources.parent.mkdir(parents=True, exist_ok=True)
                resources.write_text("resource_id\n", encoding="utf-8")
            if script.endswith("agents/planner/planner.py"):
                packages = (
                    Path(workspace) / "agents" / "planner" / "results" / "approval_packages.json"
                )
                packages.parent.mkdir(parents=True, exist_ok=True)
                packages.write_text("[]", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch(
            "backend.services.scan_service.scan_workspace_path",
            side_effect=lambda user_id, scan_id: workspace_root / str(user_id) / scan_id,
        ):
            service = ScanService(session_factory=self.scan_db, process_runner=runner)
            first = service.start_scan(user_id=1)
            second = service.start_scan(user_id=2)
            states = _await_terminal(self.scan_db, [first.scan_id, second.scan_id])

        self.assertEqual(states, {first.scan_id: "completed", second.scan_id: "completed"})
        workspaces = [
            workspace_root / str(owner) / scan.scan_id for owner, scan in ((1, first), (2, second))
        ]
        self.assertNotEqual(workspaces[0], workspaces[1])
        markers = [(path / "worker-marker.txt").read_text(encoding="utf-8") for path in workspaces]
        self.assertEqual(markers, [str(path) for path in workspaces])
        self.assertTrue(
            all((path / "workflow/history/approval_history.json").exists() for path in workspaces)
        )
        with self.scan_db() as db:
            stages = (
                db.query(ScanStage)
                .filter(ScanStage.scan_id.in_([first.scan_id, second.scan_id]))
                .all()
            )
            self.assertEqual(len(stages), 16)
            self.assertTrue(all(stage.status == "completed" for stage in stages))
            self.assertEqual(db.get(Scan, first.scan_id).user_id, 1)
            self.assertEqual(db.get(Scan, second.scan_id).user_id, 2)

    def test_failed_stage_is_persisted_without_marking_later_stages_complete(self) -> None:
        def failing_runner(*args, **kwargs):
            return SimpleNamespace(returncode=1, stdout="", stderr="synthetic stage failure")

        with patch(
            "backend.services.scan_service.scan_workspace_path",
            side_effect=lambda user_id, scan_id: self.tmp_path
            / "workspaces"
            / str(user_id)
            / scan_id,
        ):
            service = ScanService(session_factory=self.scan_db, process_runner=failing_runner)
            state = service.start_scan(user_id=1)
            result = _await_terminal(self.scan_db, [state.scan_id])

        self.assertEqual(result[state.scan_id], "failed")
        with self.scan_db() as db:
            scan = db.get(Scan, state.scan_id)
            stages = (
                db.query(ScanStage)
                .filter(ScanStage.scan_id == state.scan_id)
                .order_by(ScanStage.stage_order)
                .all()
            )
            self.assertEqual(scan.status, "failed")
            self.assertIn("synthetic stage failure", scan.error_message)
            self.assertEqual(stages[0].status, "failed")
            self.assertTrue(all(stage.status == "pending" for stage in stages[1:]))

    def test_scan_state_is_scoped_to_requesting_user(self) -> None:
        with patch(
            "backend.services.scan_service.scan_workspace_path",
            side_effect=lambda user_id, scan_id: self.tmp_path
            / "workspaces"
            / str(user_id)
            / scan_id,
        ):
            service = ScanService(
                session_factory=self.scan_db,
                process_runner=lambda *args, **kwargs: SimpleNamespace(
                    returncode=1, stdout="", stderr="stop after ownership check"
                ),
            )
            state = service.start_scan(user_id=1)
            self.assertEqual(_await_terminal(self.scan_db, [state.scan_id])[state.scan_id], "failed")
            self.assertIsNone(service.get_status(user_id=2))
            self.assertEqual(service.get_status(user_id=1).scan_id, state.scan_id)


if __name__ == "__main__":
    unittest.main()
