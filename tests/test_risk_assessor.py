import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

from agents.risk_assessor.risk_assessor import WasteScoreEngine
from agents.scout.aws_metadata import AWSInfrastructureMetadataLoader
from agents.scout.resource_exporter import is_aws_scan_mode


class WasteScoreEngineAwsCostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.forecast = pd.DataFrame(
            {
                "resource_id": ["i-test-instance", "vol-test-a", "vol-test-b"],
                "forecast_avg_cpu": [4.0, 0.0, 0.0],
                "waste_probability": ["high", "high", "high"],
            }
        )

    def test_all_inventory_costs_present_skips_empty_estimate_assignment(self) -> None:
        # Reproduces AWS scan behavior: inventory contains every forecast and
        # EBS resource, so the missing-cost Series is empty.
        costs = {resource_id: 12.5 for resource_id in self.forecast["resource_id"]}
        with patch.object(WasteScoreEngine, "_load_resource_costs", return_value=costs):
            enriched = WasteScoreEngine.enrich_forecast_data(self.forecast)

        self.assertEqual(enriched["monthly_cost"].tolist(), [12.5, 12.5, 12.5])
        self.assertEqual(len(enriched), 3)

    def test_partial_inventory_costs_estimate_only_missing_resources(self) -> None:
        costs = {"i-test-instance": 12.5}
        with patch.object(WasteScoreEngine, "_load_resource_costs", return_value=costs), patch.object(
            WasteScoreEngine, "_estimate_monthly_cost", return_value=33.0
        ) as estimate:
            enriched = WasteScoreEngine.enrich_forecast_data(self.forecast)

        self.assertEqual(enriched["monthly_cost"].tolist(), [12.5, 33.0, 33.0])
        self.assertEqual(estimate.call_count, 2)

    def test_empty_forecast_returns_empty_numeric_cost_column(self) -> None:
        empty = self.forecast.iloc[0:0].copy()
        with patch.object(WasteScoreEngine, "_load_resource_costs", return_value={}):
            enriched = WasteScoreEngine.enrich_forecast_data(empty)

        self.assertTrue(enriched.empty)
        self.assertIn("monthly_cost", enriched.columns)
        self.assertIn("waste_score", enriched.columns)

    def test_is_aws_scan_mode_and_metadata_loader_use_active_workspace(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            marker = workspace / "synthetic_data" / "scan_source.json"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({"mode": "aws", "region": "ap-south-1"}), encoding="utf-8")

            metadata_csv = workspace / "agents" / "scout" / "results" / "infrastructure_metadata.csv"
            metadata_csv.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                [
                    {
                        "resource_id": "i-workspace-ec2",
                        "environment": "production",
                        "business_critical": True,
                        "attached_to_load_balancer": False,
                        "member_of_autoscaling_group": True,
                        "owner_exists": True,
                        "recent_activity_days": 0,
                    }
                ]
            ).to_csv(metadata_csv, index=False)

            with patch.dict(os.environ, {"FINOPS_WORKSPACE_DIR": str(workspace)}):
                self.assertTrue(is_aws_scan_mode())
                loaded = AWSInfrastructureMetadataLoader().generate(["i-workspace-ec2"])
                self.assertEqual(len(loaded), 1)
                self.assertEqual(loaded.iloc[0]["environment"], "production")
                self.assertTrue(bool(loaded.iloc[0]["business_critical"]))


if __name__ == "__main__":
    unittest.main()
