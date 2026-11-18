from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.deps import get_execution_service
from backend.auth.dependencies import SIMULATION_SEED_SCAN_ID, SIMULATION_USERNAME
from backend.auth.dependencies import get_db as auth_get_db
from backend.auth.security import token_hash
from backend.db.base import Base
from backend.db.session import get_db
from backend.main import app
from backend.models.auth import User, UserSession
from backend.models.finops import (
    Anomaly, Approval, Execution, FinOpsReport, Forecast, Resource,
    Scan, ScanResourceSnapshot,
)
from backend.services.execution_service import ExecutionService


class PipelineApiIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        cls.engine = create_engine(f"sqlite:///{Path(cls.temp_dir.name) / 'owned-api.db'}", connect_args={"check_same_thread": False})
        cls.factory = sessionmaker(bind=cls.engine, expire_on_commit=False)

        def override_db():
            session = cls.factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_db
        cls._override_db = override_db

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.users: list[User] = []
        self.approvals: list[str] = []
        self.execution_ids: list[str] = []
        with self.factory() as db:
            for index in (1, 2):
                user = User(full_name=f"User {index}", username=f"pipeline-user-{index}", email=f"pipeline-{index}@example.test", password_hash="test-only-hash")
                db.add(user)
                db.flush()
                self.users.append(user)
                scan_id = str(uuid.uuid4())
                scan = Scan(scan_id=scan_id, user_id=user.id, mode="synthetic", status="completed", progress=100, message="complete")
                resource = Resource(user_id=user.id, provider="synthetic", account_id="default", region="unknown", external_id=f"resource-{index}", resource_type="cloud_resource", attributes={})
                db.add_all([scan, resource])
                db.flush()
                snapshot = ScanResourceSnapshot(user_id=user.id, scan_id=scan_id, resource_id=resource.resource_id, estimated_monthly_cost=12.5, avg_cpu=10, avg_network_in=1, avg_network_out=2, resource_label="normal", attributes={})
                db.add(snapshot)
                db.flush()
                db.add_all([
                    Anomaly(user_id=user.id, scan_id=scan_id, snapshot_id=snapshot.snapshot_id, prediction=1, anomaly_score=0.01, prediction_label="normal", result_data={"resource_id": resource.external_id, "avg_cpu": 10, "avg_network_in": 1, "avg_network_out": 2, "monthly_cost": 12.5, "resource_label": "normal", "prediction": 1, "anomaly_score": 0.01, "prediction_label": "normal"}),
                    Forecast(user_id=user.id, scan_id=scan_id, snapshot_id=snapshot.snapshot_id, utilization_category="healthy", waste_probability="low", summary_data={"resource_id": resource.external_id}, series_data={}),
                    FinOpsReport(user_id=user.id, scan_id=scan_id, report_type="forecast_dashboard", source="test", report_data={"meta": {"history_days": 30, "forecast_days": 30, "generated_from": "test"}, "stats": {"total": 0, "waste_high": 0, "waste_medium": 0, "waste_low": 0, "idle": 0, "low_usage": 0, "healthy": 0, "high_usage": 0}, "waste_distribution": [], "resources": [], "chart_data": {}}),
                    FinOpsReport(user_id=user.id, scan_id=scan_id, report_type="anomalies", source="test", report_data={"items": []}),
                    FinOpsReport(user_id=user.id, scan_id=scan_id, report_type="forecast_results", source="test", report_data={"items": []}),
                    FinOpsReport(user_id=user.id, scan_id=scan_id, report_type="risk_assessments", source="test", report_data={"items": [{"resource_id": resource.external_id, "waste_score": 0.1, "monthly_cost": 12.5, "waste_probability": "low", "environment": "test", "business_critical": False, "attached_to_load_balancer": False, "member_of_autoscaling_group": False, "owner_exists": True, "recent_activity_days": 5, "risk_score": 1, "risk_level": "low", "risk_explanation": "test", "recommendation": "Manual Review Required"}]}),
                    FinOpsReport(user_id=user.id, scan_id=scan_id, report_type="audit_results", source="test", report_data={"items": [{"resource_id": resource.external_id, "resource_type": "cloud_resource", "monthly_cost": 12.5, "annual_cost": 150, "waste_score": 0.1, "risk_level": "low", "priority_score": 1, "priority_category": "low", "potential_monthly_savings": 1, "potential_annual_savings": 12, "recommendation": "Manual Review Required"}]}),
                    FinOpsReport(user_id=user.id, scan_id=scan_id, report_type="executive_report", source="test", report_data={"executive_summary": "summary", "key_findings": [], "top_cost_drivers": [], "recommended_actions": [], "risk_considerations": [], "estimated_savings": {}, "source": "test"}),
                    FinOpsReport(user_id=user.id, scan_id=scan_id, report_type="plans", source="test", report_data={"items": []}),
                    FinOpsReport(user_id=user.id, scan_id=scan_id, report_type="scan_source", source="test", report_data={"mode": "synthetic", "resource_count": 1, "marker": f"owner-{index}"}),
                ])
                approval_id = str(uuid.uuid4())
                db.add(Approval(approval_id=approval_id, user_id=user.id, scan_id=scan_id, snapshot_id=snapshot.snapshot_id, action="stop", status="pending", risk_level="low", estimated_savings=1, business_justification="test", execution_steps=["step"]))
                self.approvals.append(approval_id)
                execution_id = str(uuid.uuid4())
                db.add(Execution(execution_id=execution_id, user_id=user.id, scan_id=scan_id, approval_id=approval_id, snapshot_id=snapshot.snapshot_id, action="stop", status="success", mode="simulation", result_data={"resource_id": resource.external_id}, log_lines=["simulation"], rollback_steps=["start"] , completed_at=datetime.now(timezone.utc)))
                self.execution_ids.append(execution_id)
            db.commit()
            self.user_ids = [user.id for user in self.users]
            self.usernames = [user.username for user in self.users]
            self.scan_ids = [db.query(Scan).filter(Scan.user_id == user.id).one().scan_id for user in self.users]
            for user in self.users:
                token = f"session-{user.id}"
                csrf = f"csrf-{user.id}"
                db.add(UserSession(user_id=user.id, token_hash=token_hash(token), csrf_token_hash=token_hash(csrf), expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
            db.commit()
        self.clients = [TestClient(app), TestClient(app)]
        for index, client in enumerate(self.clients, start=1):
            client.cookies.set("finops_session", f"session-{index}")
            client.cookies.set("finops_csrf", f"csrf-{index}")
        app.dependency_overrides[get_execution_service] = lambda: ExecutionService()

    def tearDown(self):
        for client in self.clients:
            client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides[get_db] = PipelineApiIsolationTests._override_db

    def test_all_pipeline_read_endpoints_require_authentication(self):
        endpoints = ["/resources", "/anomalies", "/forecast", "/risk", "/audit", "/audit/report", "/plans", "/waste", "/approvals", "/executions", "/scan/status", "/scan/source"]
        client = TestClient(app)
        try:
            self.assertTrue(all(client.get(path).status_code == 401 for path in endpoints))
        finally:
            client.close()

    def test_users_without_owned_scans_never_receive_legacy_artifacts(self):
        with self.factory() as db:
            user = User(full_name="New User", username="pipeline-user-new", email="pipeline-new@example.test", password_hash="test-only-hash")
            db.add(user)
            db.flush()
            token, csrf = "session-new", "csrf-new"
            db.add(UserSession(user_id=user.id, token_hash=token_hash(token), csrf_token_hash=token_hash(csrf), expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
            db.commit()
        client = TestClient(app)
        client.cookies.set("finops_session", token)
        client.cookies.set("finops_csrf", csrf)
        try:
            for path in ("/resources", "/anomalies", "/forecast", "/risk", "/audit", "/audit/report", "/plans", "/waste"):
                self.assertEqual(client.get(path).status_code, 404, path)
        finally:
            client.close()

    def test_read_apis_return_only_the_authenticated_users_scan_records(self):
        endpoints = ["/resources", "/anomalies", "/forecast", "/risk", "/audit", "/audit/report", "/plans", "/waste", "/approvals", "/executions", "/scan/source"]
        for index, client in enumerate(self.clients, start=1):
            for path in endpoints:
                response = client.get(path)
                self.assertEqual(response.status_code, 200, (path, response.text))
                self.assertNotIn(f"resource-{3-index}", response.text)
                if path == "/scan/source":
                    self.assertEqual(response.json()["marker"], f"owner-{index}")
                if path == "/resources":
                    self.assertEqual(response.json()["items"][0]["resource_id"], f"resource-{index}")

    def test_approval_and_execution_ids_cannot_cross_user_boundaries(self):
        first = self.clients[0]
        headers = {"X-CSRF-Token": "csrf-1", "Origin": "http://localhost:5173"}
        self.assertEqual(first.post(f"/approve/{self.approvals[1]}", headers=headers).status_code, 404)
        self.assertEqual(first.post(f"/reject/{self.approvals[1]}", headers=headers).status_code, 404)
        self.assertEqual(first.post(f"/execute/{self.approvals[1]}", headers=headers).status_code, 404)
        self.assertEqual(first.get(f"/executions/{self.execution_ids[1]}").status_code, 404)

    def test_approval_transition_is_owned_and_logged(self):
        client = self.clients[0]
        response = client.post(f"/approve/{self.approvals[0]}", json={"reviewer": "spoofed", "notes": "reviewed"}, headers={"X-CSRF-Token": "csrf-1", "Origin": "http://localhost:5173"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["reviewed_by"], self.usernames[0])
        with self.factory() as db:
            row = db.get(Approval, self.approvals[0])
            self.assertEqual(row.status, "approved")
            self.assertEqual(row.reviewed_by_user_id, self.user_ids[0])

    def test_execution_persists_only_against_owners_approved_record(self):
        from pathlib import Path
        temp_dir = self.temp_dir

        class SimulatedExecutor:
            def execute(self, request):
                log_path = Path(temp_dir.name) / f"simulation-{request.approval_id}.log"
                log_path.write_text("safe simulated result", encoding="utf-8")
                return SimpleNamespace(
                    execution_id=str(uuid.uuid4()), request=request, status="success", mode="simulation",
                    log_path=log_path, rollback_plan=SimpleNamespace(steps=["review rollback"]), error_message=None,
                )

        with self.factory() as db:
            db.delete(db.get(Execution, self.execution_ids[0]))
            db.commit()
        app.dependency_overrides[get_execution_service] = lambda: ExecutionService(executor=SimulatedExecutor())
        client = self.clients[0]
        headers = {"X-CSRF-Token": "csrf-1", "Origin": "http://localhost:5173"}
        approved = client.post(f"/approve/{self.approvals[0]}", headers=headers)
        self.assertEqual(approved.status_code, 200, approved.text)
        response = client.post(f"/execute/{self.approvals[0]}", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["mode"], "simulation")
        with self.factory() as db:
            record = db.query(Execution).filter(Execution.approval_id == self.approvals[0]).one()
            self.assertEqual(record.user_id, self.user_ids[0])
            self.assertEqual(record.log_lines, ["safe simulated result"])
        self.assertNotIn("resource-2", client.get("/executions").text)

    def test_simulation_mode_works_without_auth_and_never_mixes_user_data(self):
        # A legacy completed demo scan without owned rows must not block self-healing.
        with self.factory() as db:
            sim_user = User(
                full_name="Simulation Mode Demo",
                username=SIMULATION_USERNAME,
                email="simulation@finops.local",
                password_hash="!simulation-disabled!",
                is_active=False,
            )
            db.add(sim_user)
            db.flush()
            db.add(Scan(
                scan_id=SIMULATION_SEED_SCAN_ID,
                user_id=sim_user.id,
                mode="synthetic",
                status="completed",
                progress=100,
                message="legacy empty seed",
            ))
            db.commit()

        sim_client = TestClient(app)
        try:
            sim_headers = {"X-FinOps-Mode": "simulation"}
            for path in ("/resources", "/anomalies", "/forecast", "/risk", "/audit", "/audit/report", "/plans", "/waste", "/approvals", "/executions", "/scan/source"):
                response = sim_client.get(path, headers=sim_headers)
                self.assertEqual(response.status_code, 200, (path, response.text))
                self.assertNotIn("resource-1", response.text)
                self.assertNotIn("resource-2", response.text)
            self.assertGreater(sim_client.get("/resources", headers=sim_headers).json()["count"], 0)

            # Simulation mode cannot access account-only endpoints or trigger live AWS scans
            self.assertEqual(sim_client.get("/aws/accounts", headers=sim_headers).status_code, 401)
            sim_client.get("/auth/csrf")
            csrf = sim_client.cookies.get("finops_csrf")
            missing_scan_mode = sim_client.post(
                "/scan/start",
                json={},
                headers={
                    "X-FinOps-Mode": "simulation",
                    "X-CSRF-Token": csrf,
                    "Origin": "http://localhost:5173",
                },
            )
            self.assertEqual(missing_scan_mode.status_code, 422, missing_scan_mode.text)
            aws_scan = sim_client.post(
                "/scan/start",
                json={"mode": "aws"},
                headers={"X-FinOps-Mode": "simulation", "X-CSRF-Token": csrf, "Origin": "http://localhost:5173"},
            )
            self.assertEqual(aws_scan.status_code, 403)
        finally:
            sim_client.close()


