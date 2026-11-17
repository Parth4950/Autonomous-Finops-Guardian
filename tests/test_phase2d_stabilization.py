"""Regression tests for Phase 2D stabilization."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd
import yaml

from agents.scout.aws_metadata import AWSInfrastructureMetadataLoader
from agents.scout.resource_exporter import AwsResourceExporter, is_aws_scan_mode
from backend.config.deployment import cors_allow_origins
from backend.config.settings import database_connect_args, database_url


ROOT = Path(__file__).resolve().parents[1]


class Phase2DStabilizationTests(unittest.TestCase):
    def test_aws_scan_mode_and_metadata_resolve_from_active_workspace(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            marker = workspace / "synthetic_data" / "scan_source.json"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps({"mode": "aws", "region": "ap-south-1", "resource_count": 1}),
                encoding="utf-8",
            )

            metadata_path = workspace / "agents" / "scout" / "results" / "infrastructure_metadata.csv"
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                [
                    {
                        "resource_id": "i-isolated-001",
                        "environment": "staging",
                        "business_critical": False,
                        "attached_to_load_balancer": True,
                        "member_of_autoscaling_group": False,
                        "owner_exists": True,
                        "recent_activity_days": 7,
                    }
                ]
            ).to_csv(metadata_path, index=False)

            with patch.dict(os.environ, {"FINOPS_WORKSPACE_DIR": str(workspace)}, clear=False):
                self.assertTrue(is_aws_scan_mode())
                df = AWSInfrastructureMetadataLoader().generate(["i-isolated-001"])
                self.assertEqual(len(df), 1)
                self.assertEqual(df.iloc[0]["environment"], "staging")
                self.assertTrue(bool(df.iloc[0]["attached_to_load_balancer"]))

                exporter = AwsResourceExporter(
                    scout=object(),  # type: ignore[arg-type]
                    metrics_collector=object(),  # type: ignore[arg-type]
                )
                self.assertEqual(
                    exporter._metadata_csv,
                    (workspace / "agents" / "scout" / "results" / "infrastructure_metadata.csv").resolve(),
                )
                self.assertEqual(
                    exporter._scan_source_json,
                    (workspace / "synthetic_data" / "scan_source.json").resolve(),
                )

    def test_aws_scan_mode_falls_back_to_env_when_marker_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            with patch.dict(
                os.environ,
                {"FINOPS_WORKSPACE_DIR": str(workspace), "FINOPS_SCAN_MODE": "aws"},
                clear=False,
            ):
                self.assertTrue(is_aws_scan_mode())
            with patch.dict(
                os.environ,
                {"FINOPS_WORKSPACE_DIR": str(workspace), "FINOPS_SCAN_MODE": "synthetic"},
                clear=False,
            ):
                self.assertFalse(is_aws_scan_mode())

    def test_backend_dockerfile_packages_and_executes_migrations(self) -> None:
        dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY --chown=10001:10001 alembic.ini ./alembic.ini", dockerfile)
        self.assertIn("COPY --chown=10001:10001 migrations ./migrations", dockerfile)
        self.assertIn("mkdir -p /app/runtime/workspaces", dockerfile)
        self.assertIn("alembic upgrade head", dockerfile)
        self.assertIn("uvicorn backend.main:app", dockerfile)

    def test_kubernetes_manifests_configure_writable_workspaces_and_cors(self) -> None:
        deployment = yaml.safe_load((ROOT / "k8s" / "backend-deployment.yaml").read_text(encoding="utf-8"))
        init_cmd = " ".join(deployment["spec"]["template"]["spec"]["initContainers"][0]["command"])
        self.assertIn("runtime/workspaces", init_cmd)

        mounts = deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]
        mount_paths = {item["mountPath"]: item.get("subPath") for item in mounts}
        self.assertEqual(mount_paths.get("/app/runtime"), "runtime")
        self.assertEqual(mount_paths.get("/app/runtime/workspaces"), "runtime/workspaces")

        configmap = yaml.safe_load((ROOT / "k8s" / "configmap.yaml").read_text(encoding="utf-8"))
        data = configmap["data"]
        self.assertEqual(data.get("DATABASE_URL"), "sqlite:////app/runtime/finops-auth.db")
        origins = [origin.strip() for origin in data.get("CORS_ALLOW_ORIGINS", "").split(",")]
        self.assertIn("http://localhost:8080", origins)
        self.assertIn("http://127.0.0.1:8080", origins)

        with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": ""}, clear=False):
            default_origins = cors_allow_origins()
            self.assertIn("http://localhost:8080", default_origins)
            self.assertIn("http://127.0.0.1:8080", default_origins)

    def test_gitignore_and_dockerignore_cover_temp_and_runtime_artifacts(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        for pattern in (".pytest*/", "tmp*/", "runtime/", "*.db", "*.sqlite3"):
            self.assertIn(pattern, gitignore)
        for pattern in ("**/.pytest*", "tmp*", "runtime", "*.db", "*.sqlite3"):
            self.assertIn(pattern, dockerignore)

    def test_frontend_auth_cache_and_empty_state_guards_present(self) -> None:
        auth_context = (ROOT / "frontend" / "src" / "auth" / "AuthContext.tsx").read_text(encoding="utf-8")
        self.assertGreaterEqual(auth_context.count("queryClient.clear()"), 4)

        app_layout = (ROOT / "frontend" / "src" / "components" / "layout" / "AppLayout.tsx").read_text(encoding="utf-8")
        self.assertNotIn("not isolated by account yet", app_layout)
        self.assertIn("isolated to your account", app_layout)

        query_state = (ROOT / "frontend" / "src" / "components" / "shared" / "QueryState.tsx").read_text(encoding="utf-8")
        self.assertIn("isNoScanDataError", query_state)

    def test_supabase_and_render_postgres_url_normalization(self) -> None:
        supabase_pooler = (
            "postgresql://postgres.projectref:supaPass123@aws-0-ap-south-1.pooler.supabase.com:6543/"
            "postgres?pgbouncer=true"
        )
        with patch.dict(os.environ, {"DATABASE_URL": supabase_pooler}, clear=False):
            normalized = database_url()
            self.assertTrue(normalized.startswith("postgresql+psycopg2://"))
            self.assertNotIn("pgbouncer", normalized)
            self.assertIn("supaPass123", normalized)
            self.assertEqual(database_connect_args(normalized), {"sslmode": "require"})



if __name__ == "__main__":
    unittest.main()
