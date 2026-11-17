"""
Export Scout + CloudWatch discoveries into ML pipeline inputs.

Writes cloud_resources.csv, historical_cpu_usage.csv, infrastructure metadata,
and scan_source.json for downstream Isolation Forest, Prophet, and Risk agents.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.scout.aws_metadata import metadata_from_ebs, metadata_from_ec2
from agents.scout.metrics_collector import MetricsCollector
from agents.scout.scout_agent import ScoutAgent
from backend.models.paths import workspace_path
from backend.utils.aws_client import (
    AWSClientError,
    AWSConfigurationError,
    sanitize_aws_error_message,
)

logger = logging.getLogger(__name__)

SCOUT_RESULTS_DIR = workspace_path(Path(__file__).resolve().parent / "results")
DEFAULT_RESOURCES_CSV = workspace_path(_PROJECT_ROOT / "synthetic_data" / "cloud_resources.csv")
DEFAULT_HISTORICAL_CSV = workspace_path(_PROJECT_ROOT / "ml" / "forecasting" / "data" / "historical_cpu_usage.csv")
DEFAULT_METADATA_CSV = SCOUT_RESULTS_DIR / "infrastructure_metadata.csv"
DEFAULT_SCAN_SOURCE_JSON = workspace_path(_PROJECT_ROOT / "synthetic_data" / "scan_source.json")

AWS_METRICS_LOOKBACK_DAYS = 14
MAX_EC2_INSTANCES = 100

# Rough on-demand USD/month estimates (730 h) for common instance families.
INSTANCE_MONTHLY_COST_USD: dict[str, float] = {
    "t2.micro": 8.5,
    "t2.small": 17.0,
    "t2.medium": 34.0,
    "t3.micro": 7.6,
    "t3.small": 15.2,
    "t3.medium": 30.4,
    "t3.large": 60.7,
    "t3.xlarge": 121.4,
    "m5.large": 70.1,
    "m5.xlarge": 140.2,
    "m5.2xlarge": 280.4,
    "c5.large": 62.1,
    "c5.xlarge": 124.1,
    "r5.large": 91.2,
    "r5.xlarge": 182.4,
}

EBS_GB_MONTHLY_USD = 0.10


class AwsResourceExporter:
    """Discover AWS resources and map them to FinOps pipeline CSV inputs."""

    def __init__(
        self,
        scout: ScoutAgent | None = None,
        metrics_collector: MetricsCollector | None = None,
        resources_csv: Path | None = None,
        historical_csv: Path | None = None,
        metadata_csv: Path | None = None,
        scan_source_json: Path | None = None,
    ) -> None:
        self._scout = scout or ScoutAgent()
        self._metrics = metrics_collector or MetricsCollector(
            lookback_days=AWS_METRICS_LOOKBACK_DAYS
        )
        self._resources_csv = resources_csv or workspace_path(_PROJECT_ROOT / "synthetic_data" / "cloud_resources.csv")
        self._historical_csv = historical_csv or workspace_path(_PROJECT_ROOT / "ml" / "forecasting" / "data" / "historical_cpu_usage.csv")
        self._metadata_csv = metadata_csv or workspace_path(Path(__file__).resolve().parent / "results" / "infrastructure_metadata.csv")
        self._scan_source_json = scan_source_json or workspace_path(_PROJECT_ROOT / "synthetic_data" / "scan_source.json")

    def run(self) -> dict[str, Any]:
        """Execute AWS discovery and write pipeline artifacts."""
        logger.info("Starting AWS resource export in region %s", self._scout.region)

        findings = self._scout.run()
        ec2_findings = [item for item in findings if item.get("resource_type") == "ec2"]
        ebs_findings = [item for item in findings if item.get("resource_type") == "ebs"]

        if not ec2_findings and not ebs_findings:
            raise RuntimeError(
                f"No EC2 or EBS resources discovered in {self._scout.region}. "
                "Verify AWS credentials and that the region contains resources."
            )

        running_ec2 = [
            item
            for item in ec2_findings
            if item.get("state") in {"running", "stopped"} and item.get("instance_id")
        ]
        running_ec2 = running_ec2[:MAX_EC2_INSTANCES]

        metrics_by_instance: dict[str, dict[str, Any]] = {}
        history_records: list[dict[str, Any]] = []

        for index, finding in enumerate(running_ec2, start=1):
            instance_id = finding["instance_id"]
            logger.info(
                "Collecting CloudWatch metrics (%d/%d): %s",
                index,
                len(running_ec2),
                instance_id,
            )
            summary = self._metrics.collect_instance_metrics(instance_id)
            metrics_by_instance[instance_id] = summary

            cpu_series = self._metrics.get_daily_metric_series(instance_id, "CPUUtilization")
            for point in cpu_series:
                history_records.append(
                    {
                        "resource_id": instance_id,
                        "date": point.timestamp.astimezone(UTC).date().isoformat(),
                        "cpu_utilization": round(point.value, 2),
                        "resource_type": "aws",
                    }
                )

        resource_rows: list[dict[str, Any]] = []
        metadata_rows: list[dict[str, Any]] = []

        for finding in running_ec2:
            instance_id = finding["instance_id"]
            metrics = metrics_by_instance.get(instance_id, {})
            avg_cpu = _coalesce_metric(metrics.get("avg_cpu"), default=0.0)
            avg_in = _coalesce_metric(metrics.get("avg_network_in"), default=0.0)
            avg_out = _coalesce_metric(metrics.get("avg_network_out"), default=0.0)

            resource_rows.append(
                {
                    "resource_id": instance_id,
                    "avg_cpu": avg_cpu,
                    "avg_network_in": avg_in,
                    "avg_network_out": avg_out,
                    "monthly_cost": estimate_ec2_monthly_cost(finding.get("instance_type")),
                    "resource_label": infer_ec2_label(avg_cpu, finding.get("state")),
                }
            )
            metadata_rows.append(metadata_from_ec2(finding))

        for finding in ebs_findings:
            volume_id = finding.get("volume_id")
            if not volume_id:
                continue
            size_gb = float(finding.get("size") or 0)
            resource_rows.append(
                {
                    "resource_id": volume_id,
                    "avg_cpu": 0.0,
                    "avg_network_in": 0.0,
                    "avg_network_out": 0.0,
                    "monthly_cost": round(size_gb * EBS_GB_MONTHLY_USD, 2),
                    "resource_label": "zombie" if finding.get("is_unattached") else "normal",
                }
            )
            metadata_rows.append(metadata_from_ebs(finding))

        resources_df = pd.DataFrame(resource_rows)
        metadata_df = pd.DataFrame(metadata_rows)
        history_df = pd.DataFrame(history_records)

        self._resources_csv.parent.mkdir(parents=True, exist_ok=True)
        self._historical_csv.parent.mkdir(parents=True, exist_ok=True)
        self._metadata_csv.parent.mkdir(parents=True, exist_ok=True)

        resources_df.to_csv(self._resources_csv, index=False)
        metadata_df.to_csv(self._metadata_csv, index=False)

        if history_df.empty:
            logger.warning(
                "No CloudWatch CPU history collected — writing empty history header for heuristic fallback."
            )
            pd.DataFrame(
                columns=["resource_id", "date", "cpu_utilization", "resource_type"]
            ).to_csv(self._historical_csv, index=False)
        else:
            history_df.to_csv(self._historical_csv, index=False)

        account_id = os.getenv("FINOPS_AWS_ACCOUNT_ID", "").strip()
        if not account_id:
            try:
                sts = self._scout._aws_client.create_client("sts")
                caller = sts.get_caller_identity()
                account_id = str(caller.get("Account") or "").strip()
            except Exception:
                account_id = ""

        scan_source = {
            "mode": "aws",
            "account_id": account_id or "aws",
            "region": self._scout.region,
            "generated_at": datetime.now(UTC).isoformat(),
            "ec2_count": len(running_ec2),
            "ebs_count": len(ebs_findings),
            "resource_count": len(resource_rows),
            "history_rows": len(history_records),
            "metrics_lookback_days": AWS_METRICS_LOOKBACK_DAYS,
        }
        self._scan_source_json.write_text(json.dumps(scan_source, indent=2), encoding="utf-8")

        logger.info(
            "AWS export complete — %d resources, %d history rows, region=%s",
            len(resource_rows),
            len(history_records),
            self._scout.region,
        )
        return scan_source


def infer_ec2_label(avg_cpu: float, state: str | None) -> str:
    if state == "stopped":
        return "zombie"
    if avg_cpu < 5:
        return "zombie"
    if avg_cpu < 20:
        return "normal"
    return "normal"


def estimate_ec2_monthly_cost(instance_type: str | None) -> float:
    if not instance_type:
        return 50.0
    if instance_type in INSTANCE_MONTHLY_COST_USD:
        return INSTANCE_MONTHLY_COST_USD[instance_type]

    family = instance_type.split(".")[0] if "." in instance_type else instance_type
    if family.startswith(("t2", "t3", "t4g")):
        return 30.0
    if family.startswith(("m5", "m6", "m7")):
        return 120.0
    if family.startswith(("c5", "c6", "c7")):
        return 110.0
    if family.startswith(("r5", "r6", "r7")):
        return 150.0
    return 75.0


def _coalesce_metric(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return default


def _aggregate_daily_cpu(series: list[Any]) -> dict[Any, float]:
    buckets: dict[Any, list[float]] = defaultdict(list)
    for point in series:
        day = point.timestamp.astimezone(UTC).date()
        buckets[day].append(float(point.value))
    return {day: sum(values) / len(values) for day, values in sorted(buckets.items())}


def is_aws_scan_mode(project_root: Path | None = None) -> bool:
    """Return True when the active scan workspace marker indicates live AWS discovery."""
    marker = (
        workspace_path(_PROJECT_ROOT / "synthetic_data" / "scan_source.json")
        if project_root is None
        else project_root / "synthetic_data" / "scan_source.json"
    )
    if not marker.exists():
        return os.getenv("FINOPS_SCAN_MODE", "").strip().lower() == "aws"
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return payload.get("mode") == "aws"


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """CLI entrypoint for AWS resource export."""
    _configure_logging()

    try:
        summary = AwsResourceExporter().run()
        print("\n=== AWS RESOURCE EXPORT ===\n")
        print(f"Region          : {summary['region']}")
        print(f"EC2 instances   : {summary['ec2_count']}")
        print(f"EBS volumes     : {summary['ebs_count']}")
        print(f"Total resources : {summary['resource_count']}")
        print(f"CPU history rows: {summary['history_rows']}")
        print(f"\nResources CSV   : {DEFAULT_RESOURCES_CSV}")
        print(f"Historical CSV  : {DEFAULT_HISTORICAL_CSV}")
        print(f"Metadata CSV    : {DEFAULT_METADATA_CSV}")
        print(f"Scan source     : {DEFAULT_SCAN_SOURCE_JSON}")
        print()
        return 0
    except AWSConfigurationError as exc:
        logger.error("AWS configuration error: %s", sanitize_aws_error_message(exc))
        return 1
    except AWSClientError as exc:
        logger.error("AWS API error: %s", sanitize_aws_error_message(exc))
        return 1
    except Exception as exc:
        logger.error("AWS resource export failed: %s", sanitize_aws_error_message(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
