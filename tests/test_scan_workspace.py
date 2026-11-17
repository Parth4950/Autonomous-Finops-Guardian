from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.auth import User
from backend.models.finops import Scan, ScanStage
from backend.services.scan_service import ScanService


@pytest.fixture
def scan_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scan-tests.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([
            User(full_name="Scan User One", username="scan-user-one", email="one@example.test", password_hash="not-a-real-password-hash"),
            User(full_name="Scan User Two", username="scan-user-two", email="two@example.test", password_hash="not-a-real-password-hash"),
        ])
        db.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _await_terminal(factory, scan_ids, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with factory() as db:
            states = {scan.scan_id: scan.status for scan in db.query(Scan).filter(Scan.scan_id.in_(scan_ids)).all()}
        if len(states) == len(scan_ids) and all(value in {"completed", "failed"} for value in states.values()):
            return states
        time.sleep(0.02)
    raise AssertionError("scan workers did not reach a terminal state")


def test_scan_workspaces_are_isolated_for_concurrent_users(scan_db, tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspaces"
    monkeypatch.setattr(
        "backend.services.scan_service.scan_workspace_path",
        lambda user_id, scan_id: workspace_root / str(user_id) / scan_id,
    )
    barrier = threading.Barrier(2)

    def runner(command, *, env, **kwargs):
        workspace = env["FINOPS_WORKSPACE_DIR"]
        marker = workspace + "/worker-marker.txt"
        barrier.wait(timeout=5)
        from pathlib import Path
        Path(marker).parent.mkdir(parents=True, exist_ok=True)
        Path(marker).write_text(workspace, encoding="utf-8")
        script = command[1].replace("\\", "/")
        if script.endswith("synthetic_data/generate_resources.py"):
            from pathlib import Path
            root = Path(workspace)
            resources = root / "synthetic_data" / "cloud_resources.csv"
            resources.parent.mkdir(parents=True, exist_ok=True)
            resources.write_text("resource_id\n", encoding="utf-8")
        if script.endswith("agents/planner/planner.py"):
            from pathlib import Path
            packages = Path(workspace) / "agents" / "planner" / "results" / "approval_packages.json"
            packages.parent.mkdir(parents=True, exist_ok=True)
            packages.write_text("[]", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    service = ScanService(session_factory=scan_db, process_runner=runner)
    first = service.start_scan(user_id=1)
    second = service.start_scan(user_id=2)
    states = _await_terminal(scan_db, [first.scan_id, second.scan_id])

    assert states == {first.scan_id: "completed", second.scan_id: "completed"}
    workspaces = [workspace_root / str(owner) / scan.scan_id for owner, scan in ((1, first), (2, second))]
    assert workspaces[0] != workspaces[1]
    markers = [(path / "worker-marker.txt").read_text(encoding="utf-8") for path in workspaces]
    assert markers == [str(path) for path in workspaces]
    assert all((path / "workflow/history/approval_history.json").exists() for path in workspaces)
    with scan_db() as db:
        stages = db.query(ScanStage).filter(ScanStage.scan_id.in_([first.scan_id, second.scan_id])).all()
        assert len(stages) == 16
        assert all(stage.status == "completed" for stage in stages)
        assert db.get(Scan, first.scan_id).user_id == 1
        assert db.get(Scan, second.scan_id).user_id == 2


def test_failed_stage_is_persisted_without_marking_later_stages_complete(scan_db, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.scan_service.scan_workspace_path",
        lambda user_id, scan_id: tmp_path / "workspaces" / str(user_id) / scan_id,
    )

    def failing_runner(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="synthetic stage failure")

    service = ScanService(session_factory=scan_db, process_runner=failing_runner)
    state = service.start_scan(user_id=1)
    result = _await_terminal(scan_db, [state.scan_id])
    assert result[state.scan_id] == "failed"

    with scan_db() as db:
        scan = db.get(Scan, state.scan_id)
        stages = db.query(ScanStage).filter(ScanStage.scan_id == state.scan_id).order_by(ScanStage.stage_order).all()
        assert scan.status == "failed"
        assert "synthetic stage failure" in scan.error_message
        assert stages[0].status == "failed"
        assert all(stage.status == "pending" for stage in stages[1:])


def test_scan_state_is_scoped_to_requesting_user(scan_db, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.scan_service.scan_workspace_path",
        lambda user_id, scan_id: tmp_path / "workspaces" / str(user_id) / scan_id,
    )
    service = ScanService(session_factory=scan_db, process_runner=lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="stop after ownership check"))
    state = service.start_scan(user_id=1)
    assert _await_terminal(scan_db, [state.scan_id])[state.scan_id] == "failed"
    assert service.get_status(user_id=2) is None
    assert service.get_status(user_id=1).scan_id == state.scan_id
