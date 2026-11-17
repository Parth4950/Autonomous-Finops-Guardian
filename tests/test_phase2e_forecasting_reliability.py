"""Regression tests for Phase 2E: AWS Forecasting Reliability and downstream pipeline continuity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("MPLBACKEND", "Agg")

import pandas as pd

from agents.auditor.auditor import AuditorPipeline
from agents.auditor.gemini_reporter import GeminiReporter
from agents.planner.gemini_planner import GeminiPlanner
from agents.planner.planner import PlannerPipeline
from agents.risk_assessor.gemini_explainer import GeminiExplainer
from agents.risk_assessor.risk_assessor import RiskAssessmentPipeline
from ml.forecasting import export_forecast_json
from ml.forecasting.prophet_forecaster import ForecastingPipeline


class Phase2EForecastingReliabilityTests(unittest.TestCase):
    def _write_aws_marker(self, workspace: Path) -> None:
        marker = workspace / "synthetic_data" / "scan_source.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            json.dumps({"mode": "aws", "region": "ap-south-1", "resource_count": 2}),
            encoding="utf-8",
        )

    def _write_ebs_only_inventory_and_metadata(self, workspace: Path) -> None:
        self._write_aws_marker(workspace)
        resources_csv = workspace / "synthetic_data" / "cloud_resources.csv"
        resources_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {
                    "resource_id": "vol-0unattached001",
                    "avg_cpu": 0.0,
                    "avg_network_in": 0.0,
                    "avg_network_out": 0.0,
                    "monthly_cost": 25.0,
                    "resource_label": "zombie",
                },
                {
                    "resource_id": "vol-0attached002",
                    "avg_cpu": 0.0,
                    "avg_network_in": 0.0,
                    "avg_network_out": 0.0,
                    "monthly_cost": 10.0,
                    "resource_label": "normal",
                },
            ]
        ).to_csv(resources_csv, index=False)

        metadata_csv = workspace / "agents" / "scout" / "results" / "infrastructure_metadata.csv"
        metadata_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {
                    "resource_id": "vol-0unattached001",
                    "environment": "development",
                    "business_critical": False,
                    "attached_to_load_balancer": False,
                    "member_of_autoscaling_group": False,
                    "owner_exists": False,
                    "recent_activity_days": 999,
                },
                {
                    "resource_id": "vol-0attached002",
                    "environment": "production",
                    "business_critical": True,
                    "attached_to_load_balancer": False,
                    "member_of_autoscaling_group": False,
                    "owner_exists": False,
                    "recent_activity_days": 10,
                },
            ]
        ).to_csv(metadata_csv, index=False)

    def test_missing_historical_csv_generates_heuristic_fallback_inside_workspace(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            self._write_ebs_only_inventory_and_metadata(workspace)

            with patch.dict(os.environ, {"FINOPS_WORKSPACE_DIR": str(workspace)}, clear=False):
                results = ForecastingPipeline().run_from_existing_history()
                self.assertEqual(export_forecast_json.main(), 0)

            self.assertEqual(len(results), 2)
            self.assertEqual(set(results["resource_type"].tolist()), {"heuristic_fallback"})

            # Ensure historical_cpu_usage.csv was created as header-only (no fake AWS measurements)
            hist_path = workspace / "ml" / "forecasting" / "data" / "historical_cpu_usage.csv"
            self.assertTrue(hist_path.is_file())
            hist_df = pd.read_csv(hist_path)
            self.assertTrue(hist_df.empty)

            dashboard_path = workspace / "ml" / "forecasting" / "results" / "forecast_dashboard.json"
            self.assertTrue(dashboard_path.is_file())
            dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
            self.assertEqual(dashboard["meta"]["history_days"], 0)
            for item in dashboard["resources"]:
                self.assertEqual(item["resource_type"], "heuristic_fallback")
                series = dashboard["chart_data"][item["resource_id"]]
                self.assertEqual(series["historical"], [])
                self.assertEqual(len(series["forecast"]), 30)

    def test_empty_historical_csv_generates_heuristic_fallback_without_fake_history(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            self._write_ebs_only_inventory_and_metadata(workspace)
            hist_path = workspace / "ml" / "forecasting" / "data" / "historical_cpu_usage.csv"
            hist_path.parent.mkdir(parents=True, exist_ok=True)
            # Test 0-byte empty file first
            hist_path.write_text("", encoding="utf-8")

            with patch.dict(os.environ, {"FINOPS_WORKSPACE_DIR": str(workspace)}, clear=False):
                results = ForecastingPipeline().run_from_existing_history()
                self.assertEqual(len(results), 2)
                self.assertTrue((results["resource_type"] == "heuristic_fallback").all())

                # Also test header-only empty CSV
                pd.DataFrame(
                    columns=["resource_id", "date", "cpu_utilization", "resource_type"]
                ).to_csv(hist_path, index=False)
                results_header_only = ForecastingPipeline().run_from_existing_history()
                self.assertEqual(len(results_header_only), 2)
                self.assertTrue((results_header_only["resource_type"] == "heuristic_fallback").all())

    def test_ebs_only_scan_flows_through_risk_auditor_and_planner_stages(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            self._write_ebs_only_inventory_and_metadata(workspace)

            with patch.dict(
                os.environ,
                {"FINOPS_WORKSPACE_DIR": str(workspace), "GEMINI_API_KEY": ""},
                clear=False,
            ):
                ForecastingPipeline().run_from_existing_history()
                self.assertEqual(export_forecast_json.main(), 0)
                risk_df = RiskAssessmentPipeline(explainer=GeminiExplainer(api_key="")).run()
                audit_df = AuditorPipeline(reporter=GeminiReporter(api_key="")).run()
                plan_df = PlannerPipeline(gemini_planner=GeminiPlanner(api_key="")).run()

            self.assertEqual(len(risk_df), 2)
            self.assertEqual(len(audit_df), 2)
            self.assertEqual(len(plan_df), 2)

            # Verify Auditor recognized vol-* as ebs
            self.assertEqual(set(audit_df["resource_type"].tolist()), {"ebs"})

            # Verify Planner selected snapshot_and_delete for the low-risk unattached EBS volume
            # and ignore for the high-risk production business-critical EBS volume
            plans_by_id = {row["resource_id"]: row["action"] for _, row in plan_df.iterrows()}
            self.assertEqual(plans_by_id["vol-0unattached001"], "snapshot_and_delete")
            self.assertEqual(plans_by_id["vol-0attached002"], "ignore")

            # Verify approval_packages.json was written inside workspace
            packages_path = workspace / "agents" / "planner" / "results" / "approval_packages.json"
            self.assertTrue(packages_path.is_file())
            packages = json.loads(packages_path.read_text(encoding="utf-8"))
            self.assertEqual(len(packages), 2)

    def test_normal_prophet_forecasting_preserved_when_sufficient_history_exists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            self._write_aws_marker(workspace)

            resources_csv = workspace / "synthetic_data" / "cloud_resources.csv"
            resources_csv.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                [
                    {
                        "resource_id": "i-0realec2001",
                        "avg_cpu": 42.0,
                        "avg_network_in": 5000.0,
                        "avg_network_out": 4000.0,
                        "monthly_cost": 60.7,
                        "resource_label": "normal",
                    },
                    {
                        "resource_id": "vol-0companion001",
                        "avg_cpu": 0.0,
                        "avg_network_in": 0.0,
                        "avg_network_out": 0.0,
                        "monthly_cost": 15.0,
                        "resource_label": "zombie",
                    },
                ]
            ).to_csv(resources_csv, index=False)

            start_date = datetime.now(UTC).date() - timedelta(days=14)
            history_rows = [
                {
                    "resource_id": "i-0realec2001",
                    "date": (start_date + timedelta(days=day)).isoformat(),
                    "cpu_utilization": 40.0 + (day % 5),
                    "resource_type": "aws",
                }
                for day in range(14)
            ]
            hist_path = workspace / "ml" / "forecasting" / "data" / "historical_cpu_usage.csv"
            hist_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(history_rows).to_csv(hist_path, index=False)

            with patch.dict(os.environ, {"FINOPS_WORKSPACE_DIR": str(workspace)}, clear=False):
                results = ForecastingPipeline().run_from_existing_history()
                self.assertEqual(export_forecast_json.main(), 0)

            by_id = {row["resource_id"]: row for _, row in results.iterrows()}
            self.assertIn("i-0realec2001", by_id)
            self.assertIn("vol-0companion001", by_id)
            self.assertEqual(by_id["i-0realec2001"]["resource_type"], "aws")
            self.assertEqual(by_id["vol-0companion001"]["resource_type"], "heuristic_fallback")

            dashboard = json.loads(
                (workspace / "ml" / "forecasting" / "results" / "forecast_dashboard.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(dashboard["chart_data"]["i-0realec2001"]["historical"]), 14)
            self.assertEqual(dashboard["chart_data"]["vol-0companion001"]["historical"], [])


if __name__ == "__main__":
    unittest.main()
