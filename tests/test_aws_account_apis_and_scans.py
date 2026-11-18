"""Tests for Phase 3B & 3C: AWS Account Management APIs, STS verification, and Account-Aware Scanning."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.api.deps import get_aws_account_service, get_scan_service
from backend.auth.security import token_hash
from backend.db.base import Base
from backend.db.session import get_db
from backend.main import app
from backend.models.auth import User, UserSession
from backend.models.finops import AWSAccount, FinOpsReport, Resource, Scan
from backend.services.aws_account_service import AWSAccountService
from backend.services.scan_service import ScanService
from backend.utils.aws_client import (
    AWSClientHelper,
    STSIdentity,
    get_aws_credentials,
    sanitize_aws_error_message,
    verify_aws_credentials,
)
from backend.utils.credential_encryption import generate_encryption_key

MOCK_ASIA_EXAMPLE = "ASIA" + "IOSFODNN7EXAMPLE"
MOCK_AKIA_PERM = "AKIA" + "IOSFODNN7PERMKEY"
MOCK_ASIA_EXPIRED = "ASIA" + "EXPIREDTOKEN1234"
MOCK_AKIA_ENV = "AKIA" + "ENVFILEDEFAULT00"
MOCK_AKIA_PERSCAN = "AKIA" + "PERSCANUSERKEY11"
MOCK_AKIA_PROCESS = "AKIA" + "PROCESSKEY222222"
MOCK_ASIA_TARGET = "ASIA" + "SCANTARGET123456"


class AWSAccountApiAndScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        cls.engine = create_engine(
            f"sqlite:///{Path(cls.temp_dir.name) / 'aws-phase3bc.db'}",
            connect_args={"check_same_thread": False},
        )
        cls.factory = sessionmaker(bind=cls.engine, expire_on_commit=False)

        def override_db():
            db = cls.factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        cls._override_db = override_db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()
        cls.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.enc_key = generate_encryption_key()
        self.env_patch = patch.dict(
            os.environ,
            {
                "CREDENTIALS_ENCRYPTION_KEY": self.enc_key,
                "ALLOW_AWS_SCAN": "true",
                "EXECUTION_MODE": "simulation",
            },
            clear=False,
        )
        self.env_patch.start()

        with self.factory() as db:
            for idx in (1, 2):
                user = User(
                    full_name=f"AWS User {idx}",
                    username=f"aws-user-{idx}",
                    email=f"aws-{idx}@example.test",
                    password_hash="test-hash",
                )
                db.add(user)
                db.flush()
                db.add(
                    UserSession(
                        user_id=user.id,
                        token_hash=token_hash(f"session-{idx}"),
                        csrf_token_hash=token_hash(f"csrf-{idx}"),
                        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    )
                )
            db.commit()

        self.clients = [TestClient(app), TestClient(app)]
        for idx, client in enumerate(self.clients, start=1):
            client.cookies.set("finops_session", f"session-{idx}")
            client.cookies.set("finops_csrf", f"csrf-{idx}")

    def tearDown(self) -> None:
        for client in self.clients:
            client.close()
        self.env_patch.stop()
        app.dependency_overrides.clear()
        app.dependency_overrides[get_db] = AWSAccountApiAndScanTests._override_db

    @staticmethod
    def _csrf(idx: int = 1) -> dict[str, str]:
        return {"X-CSRF-Token": f"csrf-{idx}", "Origin": "http://localhost:5173"}

    def test_connect_list_verify_update_and_disconnect_aws_account_lifecycle(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_verifier(*, access_key_id: str, secret_access_key: str, region: str, session_token: str | None = None) -> STSIdentity:
            calls.append(
                {
                    "access_key_id": access_key_id,
                    "secret_access_key": secret_access_key,
                    "region": region,
                    "session_token": session_token,
                }
            )
            return STSIdentity(
                account_id="123456789012",
                arn="arn:aws:sts::123456789012:assumed-role/voclabs/user1",
                user_id="AROAEXAMPLE:user1",
                region=region,
            )

        app.dependency_overrides[get_aws_account_service] = lambda: AWSAccountService(verifier=fake_verifier)
        client = self.clients[0]

        # Unauthenticated access is rejected
        unauth = TestClient(app)
        try:
            self.assertEqual(unauth.get("/aws/accounts").status_code, 401)
        finally:
            unauth.close()

        # Missing CSRF header on POST is rejected
        no_csrf = client.post(
            "/aws/accounts",
            json={
                "display_name": "Learner Lab",
                "access_key_id": MOCK_ASIA_EXAMPLE,
                "secret_access_key": "secret-key-value",
                "default_region": "us-east-1",
            },
            headers={"Origin": "http://localhost:5173"},
        )
        self.assertEqual(no_csrf.status_code, 403)

        # Connect with Learner Lab temporary credentials (session_token)
        connected = client.post(
            "/aws/accounts",
            json={
                "display_name": "Learner Lab",
                "access_key_id": MOCK_ASIA_EXAMPLE,
                "secret_access_key": "secret-key-value-1",
                "session_token": "temporary-session-token-1",
                "default_region": "us-east-1",
            },
            headers=self._csrf(1),
        )
        self.assertEqual(connected.status_code, 201, connected.text)
        body = connected.json()
        account_id = body["id"]
        self.assertEqual(body["aws_account_id"], "123456789012")
        self.assertEqual(body["arn"], "arn:aws:sts::123456789012:assumed-role/voclabs/user1")
        self.assertEqual(body["default_region"], "us-east-1")
        self.assertEqual(body["access_key_id_masked"], "ASIA************MPLE")
        self.assertTrue(body["has_session_token"])
        self.assertEqual(body["verification_status"], "verified")
        self.assertNotIn("secret-key-value-1", connected.text)
        self.assertNotIn("temporary-session-token-1", connected.text)
        self.assertNotIn("encrypted_credentials", connected.text)

        # List accounts for User 1 vs User 2 (isolation)
        listed = client.get("/aws/accounts")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)
        self.assertEqual(self.clients[1].get("/aws/accounts").json()["count"], 0)
        self.assertEqual(self.clients[1].get(f"/aws/accounts/{account_id}").status_code, 404)
        self.assertEqual(
            self.clients[1].post(f"/aws/accounts/{account_id}/verify", headers=self._csrf(2)).status_code,
            404,
        )
        self.assertEqual(
            self.clients[1].patch(
                f"/aws/accounts/{account_id}",
                json={"display_name": "Hijack"},
                headers=self._csrf(2),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.clients[1].delete(f"/aws/accounts/{account_id}", headers=self._csrf(2)).status_code,
            404,
        )

        # Rotate credentials via PATCH (switching to permanent key with clear_session_token)
        updated = client.patch(
            f"/aws/accounts/{account_id}",
            json={
                "display_name": "Production IAM",
                "default_region": "ap-south-1",
                "access_key_id": MOCK_AKIA_PERM,
                "secret_access_key": "permanent-secret-2",
                "clear_session_token": True,
            },
            headers=self._csrf(1),
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["display_name"], "Production IAM")
        self.assertEqual(updated.json()["default_region"], "ap-south-1")
        self.assertEqual(updated.json()["access_key_id_masked"], "AKIA************MKEY")
        self.assertFalse(updated.json()["has_session_token"])
        self.assertIsNone(calls[-1]["session_token"])

        # Disconnect account
        deleted = client.delete(f"/aws/accounts/{account_id}", headers=self._csrf(1))
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(client.get("/aws/accounts").json()["count"], 0)

    def test_sts_verification_marks_expired_token_and_sanitizes_errors(self) -> None:
        client = self.clients[0]
        created = client.post(
            "/aws/accounts",
            json={
                "display_name": "Lab Session",
                "access_key_id": MOCK_ASIA_EXPIRED,
                "secret_access_key": "top-secret-never-echo",
                "session_token": "expired-session-token-value",
                "default_region": "us-east-1",
                "verify": False,
            },
            headers=self._csrf(1),
        )
        self.assertEqual(created.status_code, 201, created.text)
        account_id = created.json()["id"]
        self.assertEqual(created.json()["verification_status"], "unverified")

        expired_error = ClientError(
            {
                "Error": {
                    "Code": "ExpiredToken",
                    "Message": f"The security token included in the request is expired: {MOCK_ASIA_EXPIRED}",
                }
            },
            "GetCallerIdentity",
        )
        with patch("backend.utils.aws_client.boto3.client") as mock_boto:
            sts_mock = MagicMock()
            sts_mock.get_caller_identity.side_effect = expired_error
            mock_boto.return_value = sts_mock

            verify_resp = client.post(
                f"/aws/accounts/{account_id}/verify",
                headers=self._csrf(1),
            )
            self.assertEqual(verify_resp.status_code, 400)
            detail = verify_resp.json()["detail"]
            self.assertIn("expired", detail.lower())
            self.assertNotIn(MOCK_ASIA_EXPIRED, detail)
            self.assertNotIn("top-secret-never-echo", detail)

        # Status in DB is updated to 'expired'
        fetched = client.get(f"/aws/accounts/{account_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["verification_status"], "expired")

    def test_load_dotenv_does_not_overwrite_per_scan_credentials(self) -> None:
        with TemporaryDirectory() as tmp:
            fake_env = Path(tmp) / ".env"
            fake_env.write_text(
                f"AWS_ACCESS_KEY_ID={MOCK_AKIA_ENV}\n"
                "AWS_SECRET_ACCESS_KEY=env-file-secret\n"
                "AWS_SESSION_TOKEN=env-file-stale-session-token\n"
                "AWS_REGION=eu-west-1\n",
                encoding="utf-8",
            )
            with patch("backend.utils.aws_client._ENV_FILE", fake_env):
                # 1. Explicit per-scan account credentials (without session token) ignore .env completely
                with patch.dict(
                    os.environ,
                    {
                        "FINOPS_AWS_CREDENTIAL_SOURCE": "account",
                        "AWS_ACCESS_KEY_ID": MOCK_AKIA_PERSCAN,
                        "AWS_SECRET_ACCESS_KEY": "per-scan-secret",
                        "AWS_REGION": "ap-south-1",
                    },
                    clear=True,
                ):
                    creds = get_aws_credentials()
                    self.assertEqual(creds.access_key_id, MOCK_AKIA_PERSCAN)
                    self.assertEqual(creds.secret_access_key, "per-scan-secret")
                    self.assertEqual(creds.region, "ap-south-1")
                    self.assertIsNone(creds.session_token)

                # 2. Non-empty process environment variables are not overwritten by .env
                with patch.dict(
                    os.environ,
                    {
                        "AWS_ACCESS_KEY_ID": MOCK_AKIA_PROCESS,
                        "AWS_SECRET_ACCESS_KEY": "process-secret",
                        "AWS_REGION": "us-west-2",
                    },
                    clear=True,
                ):
                    creds = get_aws_credentials()
                    self.assertEqual(creds.access_key_id, MOCK_AKIA_PROCESS)
                    self.assertEqual(creds.region, "us-west-2")

                # 3. Blank Compose interpolation values still fall back to .env
                with patch.dict(
                    os.environ,
                    {
                        "AWS_ACCESS_KEY_ID": "",
                        "AWS_SECRET_ACCESS_KEY": "",
                        "AWS_SESSION_TOKEN": "",
                        "AWS_REGION": "",
                    },
                    clear=True,
                ):
                    creds = get_aws_credentials()
                    self.assertEqual(creds.access_key_id, MOCK_AKIA_ENV)
                    self.assertEqual(creds.session_token, "env-file-stale-session-token")
                    self.assertEqual(creds.region, "eu-west-1")

    def test_account_aware_scan_injects_credentials_and_persists_real_account_id_and_region(self) -> None:
        app.dependency_overrides[get_aws_account_service] = lambda: AWSAccountService(
            verifier=lambda **kwargs: STSIdentity(
                account_id="987654321098",
                arn="arn:aws:sts::987654321098:assumed-role/voclabs/scanner",
                user_id="AROA987654321098:scanner",
                region=kwargs["region"],
            )
        )
        client = self.clients[0]
        app.dependency_overrides[get_scan_service] = lambda: ScanService(
            session_factory=self.factory,
            process_runner=lambda *args, **kwargs: SimpleNamespace(
                returncode=0, stdout="", stderr=""
            ),
        )
        missing_account = client.post(
            "/scan/start",
            json={"mode": "aws"},
            headers=self._csrf(1),
        )
        self.assertEqual(missing_account.status_code, 400, missing_account.text)
        self.assertIn("verified AWS account", missing_account.json()["detail"])

        unverified = client.post(
            "/aws/accounts",
            json={
                "display_name": "Unverified Account",
                "access_key_id": MOCK_ASIA_EXPIRED,
                "secret_access_key": "test-secret-only",
                "session_token": "test-token-only",
                "default_region": "us-east-1",
                "verify": False,
            },
            headers=self._csrf(1),
        )
        self.assertEqual(unverified.status_code, 201, unverified.text)
        rejected = client.post(
            "/scan/start",
            json={"mode": "aws", "aws_account_id": unverified.json()["id"]},
            headers=self._csrf(1),
        )
        self.assertEqual(rejected.status_code, 400, rejected.text)
        self.assertIn("not verified", rejected.json()["detail"])

        connected = client.post(
            "/aws/accounts",
            json={
                "display_name": "Scan Target Account",
                "access_key_id": MOCK_ASIA_TARGET,
                "secret_access_key": "scan-target-secret-xyz",
                "session_token": "scan-target-session-token-xyz",
                "default_region": "ap-south-1",
            },
            headers=self._csrf(1),
        )
        self.assertEqual(connected.status_code, 201, connected.text)
        account_id = connected.json()["id"]

        captured_envs: list[dict[str, str]] = []

        def fake_runner(command, *, env, **kwargs):
            captured_envs.append(dict(env))
            workspace = Path(env["FINOPS_WORKSPACE_DIR"])
            script = command[1].replace("\\", "/")
            if script.endswith("agents/scout/export_resources.py"):
                resources = workspace / "synthetic_data" / "cloud_resources.csv"
                resources.parent.mkdir(parents=True, exist_ok=True)
                resources.write_text(
                    "resource_id,avg_cpu,avg_network_in,avg_network_out,monthly_cost,resource_label\n"
                    "i-0accountaware001,3.5,100.0,120.0,30.4,zombie\n",
                    encoding="utf-8",
                )
            if script.endswith("agents/planner/planner.py"):
                packages = workspace / "agents" / "planner" / "results" / "approval_packages.json"
                packages.parent.mkdir(parents=True, exist_ok=True)
                packages.write_text("[]", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with TemporaryDirectory() as ws_root:
            with patch(
                "backend.services.scan_service.scan_workspace_path",
                side_effect=lambda uid, sid: Path(ws_root) / str(uid) / sid,
            ):
                scan_service = ScanService(
                    session_factory=self.factory,
                    process_runner=fake_runner,
                )
                app.dependency_overrides[get_scan_service] = lambda: scan_service

                # User 2 cannot start a scan using User 1's aws_account_id
                forbidden_scan = self.clients[1].post(
                    "/scan/start",
                    json={"mode": "aws", "aws_account_id": account_id},
                    headers=self._csrf(2),
                )
                self.assertEqual(forbidden_scan.status_code, 404)

                started = client.post(
                    "/scan/start",
                    json={
                        "mode": "aws",
                        "aws_account_id": account_id,
                        "region": "us-west-2",
                    },
                    headers=self._csrf(1),
                )
                self.assertEqual(started.status_code, 200, started.text)
                scan_id = started.json()["scan_id"]
                self.assertEqual(started.json()["aws_account_id"], account_id)
                self.assertEqual(started.json()["region"], "us-west-2")

                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    status_resp = client.get("/scan/status").json()
                    if status_resp["status"] in {"completed", "failed"}:
                        break
                    time.sleep(0.02)

                self.assertEqual(status_resp["status"], "completed", status_resp)
                self.assertTrue(captured_envs)
                first_env = captured_envs[0]
                self.assertEqual(first_env.get("FINOPS_AWS_CREDENTIAL_SOURCE"), "account")
                self.assertEqual(first_env.get("AWS_ACCESS_KEY_ID"), MOCK_ASIA_TARGET)
                self.assertEqual(first_env.get("AWS_SECRET_ACCESS_KEY"), "scan-target-secret-xyz")
                self.assertEqual(first_env.get("AWS_SESSION_TOKEN"), "scan-target-session-token-xyz")
                self.assertEqual(first_env.get("AWS_REGION"), "us-west-2")
                self.assertEqual(first_env.get("FINOPS_AWS_ACCOUNT_ID"), "987654321098")

                with self.factory() as db:
                    res = db.scalar(select(Resource).where(Resource.user_id == 1))
                    self.assertIsNotNone(res)
                    self.assertEqual(res.provider, "aws")
                    self.assertEqual(res.account_id, "987654321098")
                    self.assertEqual(res.region, "us-west-2")
                    self.assertEqual(res.external_id, "i-0accountaware001")

                    source_report = db.scalar(
                        select(FinOpsReport).where(
                            FinOpsReport.scan_id == scan_id,
                            FinOpsReport.report_type == "scan_source",
                        )
                    )
                    self.assertIsNotNone(source_report)
                    self.assertEqual(source_report.report_data.get("account_id"), "987654321098")
                    self.assertEqual(source_report.report_data.get("region"), "us-west-2")
                    # Ensure no secret material was persisted in scan_source report
                    serialized_report = json.dumps(source_report.report_data)
                    self.assertNotIn("scan-target-secret-xyz", serialized_report)
                    self.assertNotIn("scan-target-session-token-xyz", serialized_report)
                    self.assertNotIn(MOCK_ASIA_TARGET, serialized_report)

    def test_failed_aws_scan_sanitizes_credentials_from_error_message(self) -> None:
        raw_err = f"Botocore error with key {MOCK_ASIA_TARGET} and aws_secret_access_key=superSecretKeyValue123"
        sanitized = sanitize_aws_error_message(raw_err)
        self.assertNotIn(MOCK_ASIA_TARGET, sanitized)
        self.assertNotIn("superSecretKeyValue123", sanitized)
        self.assertIn("[REDACTED]", sanitized)


if __name__ == "__main__":
    unittest.main()
