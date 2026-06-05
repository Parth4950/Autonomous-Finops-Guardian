"""EBS volume discovery scanner."""

from __future__ import annotations

import logging
from typing import Any

from botocore.exceptions import ClientError

from backend.utils.aws_client import AWSClientError, AWSClientHelper

logger = logging.getLogger(__name__)


class EBSScanner:
    """
    Discover EBS volumes in the configured AWS region.

    Uses the EC2 DescribeVolumes API to collect volume metadata and
    flag unattached volumes (state ``available``).
    """

    UNATTACHED_STATE = "available"

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
        Retrieve all EBS volumes in the configured region.

        Returns:
            A list of dictionaries, one per EBS volume. Each entry includes
            an ``is_unattached`` flag when ``state == 'available'``.

        Raises:
            AWSClientError: If the DescribeVolumes API call fails.
        """
        logger.info("Starting EBS scan in region: %s", self.region)

        try:
            volumes = self._fetch_all_volumes()
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            error_message = exc.response.get("Error", {}).get("Message", str(exc))
            raise AWSClientError(
                f"EBS DescribeVolumes failed [{error_code}]: {error_message}"
            ) from exc

        unattached_count = sum(1 for volume in volumes if volume["is_unattached"])
        logger.info(
            "EBS scan complete — found %d volume(s), %d unattached",
            len(volumes),
            unattached_count,
        )
        return volumes

    def _fetch_all_volumes(self) -> list[dict[str, Any]]:
        """Paginate through DescribeVolumes and normalize results."""
        paginator = self._ec2_client.get_paginator("describe_volumes")
        results: list[dict[str, Any]] = []

        for page in paginator.paginate():
            for volume in page.get("Volumes", []):
                results.append(self._normalize_volume(volume))

        return results

    @staticmethod
    def _normalize_volume(volume: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw EBS volume response into a scout finding dict."""
        state = volume.get("State")
        is_unattached = state == EBSScanner.UNATTACHED_STATE

        return {
            "resource_type": "ebs",
            "volume_id": volume.get("VolumeId"),
            "volume_type": volume.get("VolumeType"),
            "size": volume.get("Size"),
            "state": state,
            "availability_zone": volume.get("AvailabilityZone"),
            "is_unattached": is_unattached,
        }
