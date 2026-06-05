"""EC2 instance discovery scanner."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from botocore.exceptions import ClientError

from backend.utils.aws_client import AWSClientError, AWSClientHelper

logger = logging.getLogger(__name__)


class EC2Scanner:
    """
    Discover EC2 instances in the configured AWS region.

    Uses the EC2 DescribeInstances API to collect instance metadata
    including type, state, launch time, and tags.
    """

    def __init__(self, aws_client: AWSClientHelper | None = None) -> None:
        """
        Initialize the scanner.

        Args:
            aws_client: Optional shared AWS client helper. A new instance
                is created when none is provided.
        """
        self._aws_client = aws_client or AWSClientHelper()
        self._ec2_client = self._aws_client.create_client("ec2")

    @property
    def region(self) -> str:
        """Return the AWS region being scanned."""
        return self._aws_client.region

    def scan(self) -> list[dict[str, Any]]:
        """
        Retrieve all EC2 instances in the configured region.

        Returns:
            A list of dictionaries, one per EC2 instance.

        Raises:
            AWSClientError: If the DescribeInstances API call fails.
        """
        logger.info("Starting EC2 scan in region: %s", self.region)

        try:
            instances = self._fetch_all_instances()
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            error_message = exc.response.get("Error", {}).get("Message", str(exc))
            raise AWSClientError(
                f"EC2 DescribeInstances failed [{error_code}]: {error_message}"
            ) from exc

        logger.info("EC2 scan complete — found %d instance(s)", len(instances))
        return instances

    def _fetch_all_instances(self) -> list[dict[str, Any]]:
        """Paginate through DescribeInstances and normalize results."""
        paginator = self._ec2_client.get_paginator("describe_instances")
        results: list[dict[str, Any]] = []

        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    results.append(self._normalize_instance(instance))

        return results

    @staticmethod
    def _normalize_instance(instance: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw EC2 instance response into a scout finding dict."""
        launch_time = instance.get("LaunchTime")
        launch_time_str: str | None = None

        if isinstance(launch_time, datetime):
            launch_time_str = launch_time.isoformat()

        tags = {
            tag["Key"]: tag["Value"]
            for tag in instance.get("Tags", [])
            if "Key" in tag and "Value" in tag
        }

        return {
            "resource_type": "ec2",
            "instance_id": instance.get("InstanceId"),
            "instance_type": instance.get("InstanceType"),
            "state": instance.get("State", {}).get("Name"),
            "launch_time": launch_time_str,
            "tags": tags,
            "availability_zone": instance.get("Placement", {}).get("AvailabilityZone"),
        }
