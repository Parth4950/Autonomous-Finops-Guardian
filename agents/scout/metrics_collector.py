"""
CloudWatch metrics collector for EC2 instances.

Retrieves CPU and network utilization metrics over a configurable
lookback window and computes aggregated averages for downstream
ML and risk analysis agents.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Allow `python agents/scout/metrics_collector.py` from any working directory.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from botocore.exceptions import ClientError

from agents.scout.ec2_scanner import EC2Scanner
from backend.utils.aws_client import AWSClientError, AWSClientHelper, AWSConfigurationError

logger = logging.getLogger(__name__)

EC2_METRICS_NAMESPACE = "AWS/EC2"
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_METRIC_PERIOD_SECONDS = 3600  # 1 hour — keeps 7-day queries under API limits

METRIC_DEFINITIONS: dict[str, str] = {
    "CPUUtilization": "avg_cpu",
    "NetworkIn": "avg_network_in",
    "NetworkOut": "avg_network_out",
}


@dataclass(frozen=True)
class MetricDatapoint:
    """Single CloudWatch metric observation."""

    timestamp: datetime
    value: float


@dataclass(frozen=True)
class InstanceMetricsSummary:
    """Aggregated CloudWatch metrics for one EC2 instance."""

    instance_id: str
    avg_cpu: float | None
    avg_network_in: float | None
    avg_network_out: float | None
    lookback_days: int
    datapoint_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "instance_id": self.instance_id,
            "avg_cpu": self._round(self.avg_cpu),
            "avg_network_in": self._round(self.avg_network_in),
            "avg_network_out": self._round(self.avg_network_out),
            "lookback_days": self.lookback_days,
            "datapoint_counts": self.datapoint_counts,
        }

    @staticmethod
    def _round(value: float | None) -> float | None:
        """Round metric averages to two decimal places."""
        if value is None:
            return None
        return round(value, 2)


class MetricsCollector:
    """
    Collect and aggregate CloudWatch metrics for EC2 instances.

    Designed for reuse by Isolation Forest (feature vectors), Prophet
    (time-series history), and Risk Assessment (utilization thresholds).
    """

    def __init__(
        self,
        aws_client: AWSClientHelper | None = None,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        period_seconds: int = DEFAULT_METRIC_PERIOD_SECONDS,
    ) -> None:
        """
        Initialize the metrics collector.

        Args:
            aws_client: Shared AWS client helper for CloudWatch access.
            lookback_days: Number of days of historical metrics to retrieve.
            period_seconds: CloudWatch aggregation period in seconds.
        """
        self._aws_client = aws_client or AWSClientHelper()
        self._cloudwatch_client = self._aws_client.create_client("cloudwatch")
        self._lookback_days = lookback_days
        self._period_seconds = period_seconds

    @property
    def region(self) -> str:
        """Return the AWS region used for metric collection."""
        return self._aws_client.region

    @property
    def lookback_days(self) -> int:
        """Return the configured metrics lookback window in days."""
        return self._lookback_days

    def collect_instance_metrics(self, instance_id: str) -> dict[str, Any]:
        """
        Collect averaged CloudWatch metrics for a single EC2 instance.

        Args:
            instance_id: EC2 instance identifier (e.g. ``i-0abc123``).

        Returns:
            Dictionary with instance ID and average CPU/network metrics.

        Raises:
            AWSClientError: If CloudWatch API calls fail.
            ValueError: If instance_id is empty.
        """
        if not instance_id or not instance_id.strip():
            raise ValueError("instance_id is required and cannot be empty.")

        instance_id = instance_id.strip()
        logger.info(
            "Collecting %d-day CloudWatch metrics for instance: %s",
            self._lookback_days,
            instance_id,
        )

        datapoint_counts: dict[str, int] = {}
        averages: dict[str, float | None] = {}

        for metric_name, output_key in METRIC_DEFINITIONS.items():
            series = self.get_metric_series(instance_id, metric_name)
            datapoint_counts[metric_name] = len(series)
            averages[output_key] = self.calculate_average(series)

        summary = InstanceMetricsSummary(
            instance_id=instance_id,
            avg_cpu=averages["avg_cpu"],
            avg_network_in=averages["avg_network_in"],
            avg_network_out=averages["avg_network_out"],
            lookback_days=self._lookback_days,
            datapoint_counts=datapoint_counts,
        )

        logger.info(
            "Metrics collected for %s — CPU avg: %s, NetworkIn avg: %s, NetworkOut avg: %s",
            instance_id,
            summary.avg_cpu,
            summary.avg_network_in,
            summary.avg_network_out,
        )

        return summary.to_dict()

    def collect_for_instances(self, instance_ids: list[str]) -> list[dict[str, Any]]:
        """
        Collect metrics for multiple EC2 instances.

        Args:
            instance_ids: List of EC2 instance identifiers.

        Returns:
            List of metric summary dictionaries, one per instance.
        """
        results: list[dict[str, Any]] = []

        for instance_id in instance_ids:
            try:
                results.append(self.collect_instance_metrics(instance_id))
            except (AWSClientError, ValueError) as exc:
                logger.error(
                    "Failed to collect metrics for %s: %s",
                    instance_id,
                    exc,
                )
                results.append(
                    {
                        "instance_id": instance_id,
                        "avg_cpu": None,
                        "avg_network_in": None,
                        "avg_network_out": None,
                        "error": str(exc),
                    }
                )

        return results

    def get_metric_series(
        self,
        instance_id: str,
        metric_name: str,
        lookback_days: int | None = None,
    ) -> list[MetricDatapoint]:
        """
        Retrieve raw CloudWatch metric datapoints for time-series analysis.

        Reusable by Prophet forecasting and anomaly detection pipelines
        that need the full historical series rather than a single average.

        Args:
            instance_id: EC2 instance identifier.
            metric_name: CloudWatch metric name (e.g. ``CPUUtilization``).
            lookback_days: Optional override for the lookback window.

        Returns:
            Chronologically sorted list of MetricDatapoint objects.

        Raises:
            AWSClientError: If the CloudWatch API call fails.
        """
        start_time, end_time = self._get_time_range(lookback_days)
        raw_datapoints = self._fetch_metric_statistics(
            instance_id=instance_id,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
        )

        series = [
            MetricDatapoint(
                timestamp=point["Timestamp"],
                value=float(point["Average"]),
            )
            for point in raw_datapoints
            if "Timestamp" in point and "Average" in point
        ]
        series.sort(key=lambda point: point.timestamp)

        logger.debug(
            "Retrieved %d datapoints for %s/%s",
            len(series),
            instance_id,
            metric_name,
        )
        return series

    def build_feature_vector(self, instance_id: str) -> dict[str, float | None]:
        """
        Build a flat feature vector for ML models such as Isolation Forest.

        Args:
            instance_id: EC2 instance identifier.

        Returns:
            Dictionary mapping feature names to averaged metric values.
        """
        metrics = self.collect_instance_metrics(instance_id)
        return {
            "avg_cpu": metrics.get("avg_cpu"),
            "avg_network_in": metrics.get("avg_network_in"),
            "avg_network_out": metrics.get("avg_network_out"),
        }

    def get_time_series_payload(
        self,
        instance_id: str,
        lookback_days: int | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Export full metric time series for Prophet and similar forecasters.

        Args:
            instance_id: EC2 instance identifier.
            lookback_days: Optional override for the lookback window.

        Returns:
            Dictionary keyed by metric name, each value a list of
            ``{"timestamp": iso_str, "value": float}`` records.
        """
        payload: dict[str, list[dict[str, Any]]] = {}

        for metric_name in METRIC_DEFINITIONS:
            series = self.get_metric_series(
                instance_id=instance_id,
                metric_name=metric_name,
                lookback_days=lookback_days,
            )
            payload[metric_name] = [
                {
                    "timestamp": point.timestamp.isoformat(),
                    "value": round(point.value, 4),
                }
                for point in series
            ]

        return payload

    @staticmethod
    def calculate_average(series: list[MetricDatapoint]) -> float | None:
        """
        Compute the mean value across a metric time series.

        Args:
            series: List of MetricDatapoint observations.

        Returns:
            Average value rounded to two decimals, or ``None`` if empty.
        """
        if not series:
            return None

        average = sum(point.value for point in series) / len(series)
        return round(average, 2)

    def _get_time_range(
        self,
        lookback_days: int | None = None,
    ) -> tuple[datetime, datetime]:
        """Return UTC start and end times for the metrics query window."""
        days = lookback_days if lookback_days is not None else self._lookback_days
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)
        return start_time, end_time

    def _fetch_metric_statistics(
        self,
        instance_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """
        Call CloudWatch GetMetricStatistics for a single EC2 metric.

        Args:
            instance_id: EC2 instance identifier.
            metric_name: CloudWatch metric name.
            start_time: Query window start (UTC).
            end_time: Query window end (UTC).

        Returns:
            Raw datapoint dictionaries from the CloudWatch response.

        Raises:
            AWSClientError: If the API call fails.
        """
        try:
            response = self._cloudwatch_client.get_metric_statistics(
                Namespace=EC2_METRICS_NAMESPACE,
                MetricName=metric_name,
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=self._period_seconds,
                Statistics=["Average"],
            )
            return response.get("Datapoints", [])

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            error_message = exc.response.get("Error", {}).get("Message", str(exc))
            raise AWSClientError(
                f"CloudWatch GetMetricStatistics failed for {instance_id}/"
                f"{metric_name} [{error_code}]: {error_message}"
            ) from exc


def format_metrics_report(metrics: list[dict[str, Any]]) -> str:
    """
    Format collected metrics for human-readable console output.

    Args:
        metrics: List of metric summary dictionaries.

    Returns:
        A formatted multi-line string.
    """
    if not metrics:
        return "No EC2 instances found — nothing to collect metrics for."

    lines: list[str] = []

    for index, entry in enumerate(metrics, start=1):
        lines.append(f"--- Instance {index} ---")
        lines.append(f"Instance ID: {entry.get('instance_id')}")
        lines.append(f"Avg CPU (%): {entry.get('avg_cpu')}")
        lines.append(f"Avg Network In (bytes): {entry.get('avg_network_in')}")
        lines.append(f"Avg Network Out (bytes): {entry.get('avg_network_out')}")

        if "lookback_days" in entry:
            lines.append(f"Lookback (days): {entry.get('lookback_days')}")

        if entry.get("error"):
            lines.append(f"Error: {entry.get('error')}")

        lines.append("")

    return "\n".join(lines).rstrip()


def _configure_logging() -> None:
    """Configure root logging for CLI execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """
    Discover EC2 instances via Scout and print CloudWatch metrics.

    Returns:
        0 on success, 1 on failure.
    """
    _configure_logging()

    try:
        aws_client = AWSClientHelper()
        ec2_scanner = EC2Scanner(aws_client=aws_client)
        metrics_collector = MetricsCollector(aws_client=aws_client)

        instances = ec2_scanner.scan()
        instance_ids = [
            instance["instance_id"]
            for instance in instances
            if instance.get("instance_id")
        ]

        if not instance_ids:
            print("\n=== CLOUDWATCH METRICS ===\n")
            print("No EC2 instances discovered in region:", aws_client.region)
            return 0

        metrics = metrics_collector.collect_for_instances(instance_ids)

        print("\n=== CLOUDWATCH METRICS ===\n")
        print(format_metrics_report(metrics))
        print(f"\nTotal instances measured: {len(metrics)}")
        return 0

    except AWSConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    except AWSClientError as exc:
        logger.error("AWS error: %s", exc)
        return 1

    except Exception as exc:
        logger.exception("Unexpected metrics collector error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
