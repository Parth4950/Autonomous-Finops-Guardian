import unittest
from unittest.mock import patch

import pandas as pd

from agents.risk_assessor.risk_assessor import WasteScoreEngine


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


if __name__ == "__main__":
    unittest.main()
