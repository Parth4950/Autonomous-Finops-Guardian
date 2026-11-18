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

    def test_health_reports_hosted_live_scan_capability_and_render_revision(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EXECUTION_MODE": "simulation",
                "ALLOW_AWS_SCAN": "true",
                "DEPLOYMENT_ENV": "hosted",
                "RENDER": "true",
                "RENDER_GIT_COMMIT": "1234567890abcdef",
            },
        ):
            response = health_check()

        self.assertEqual(response.deployment, "hosted")
        self.assertTrue(response.aws_scan_enabled)
        self.assertEqual(response.revision, "1234567890ab")


if __name__ == "__main__":
    unittest.main()
