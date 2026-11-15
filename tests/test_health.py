"""Credential-free contract check for the existing health endpoint."""

import os
import unittest
from unittest.mock import patch

from backend.api.health import health_check


class HealthEndpointTests(unittest.TestCase):
    def test_health_reports_healthy_simulation_without_live_aws(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EXECUTION_MODE": "simulation",
                "ALLOW_AWS_SCAN": "false",
                "DEPLOYMENT_ENV": "",
                "RENDER": "",
            },
        ):
            response = health_check()

        self.assertEqual(response.status, "healthy")
        self.assertEqual(response.execution_mode, "simulation")
        self.assertFalse(response.aws_scan_enabled)


if __name__ == "__main__":
    unittest.main()
