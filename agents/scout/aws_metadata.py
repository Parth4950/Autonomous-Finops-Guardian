"""Extract risk-assessor infrastructure metadata from AWS scout findings."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

logger = logging.getLogger(__name__)

Environment = Literal["production", "staging", "development"]

DEFAULT_METADATA_CSV = (
    Path(__file__).resolve().parent / "results" / "infrastructure_metadata.csv"
)

ENV_TAG_KEYS = ("Environment", "environment", "env", "Env", "stage")
OWNER_TAG_KEYS = ("Owner", "owner", "team", "Team", "Contact")
CRITICAL_TAG_KEYS = ("BusinessCritical", "business-critical", "critical", "Critical")


def _tag_value(tags: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in tags and tags[key].strip():
            return tags[key].strip()
    return None


def _normalize_environment(raw: str | None) -> Environment:
    if not raw:
        return "development"
    value = raw.strip().lower()
    if value in {"prod", "production", "prd"}:
        return "production"
    if value in {"stage", "staging", "stg", "uat", "preprod"}:
        return "staging"
    return "development"


def _parse_launch_days(launch_time: str | None) -> int:
    if not launch_time:
        return 999
    try:
        normalized = launch_time.replace("Z", "+00:00")
        launched = datetime.fromisoformat(normalized)
        if launched.tzinfo is None:
            launched = launched.replace(tzinfo=UTC)
        delta = datetime.now(UTC) - launched.astimezone(UTC)
        return max(int(delta.total_seconds() // 86_400), 0)
    except ValueError:
        return 999


def metadata_from_ec2(finding: dict[str, Any]) -> dict[str, Any]:
    """Build risk metadata row from an EC2 scout finding."""
    tags = finding.get("tags") or {}
    env_raw = _tag_value(tags, ENV_TAG_KEYS)
    owner = _tag_value(tags, OWNER_TAG_KEYS)
    critical_raw = _tag_value(tags, CRITICAL_TAG_KEYS)

    business_critical = False
    if critical_raw:
        business_critical = critical_raw.lower() in {"true", "yes", "1", "critical"}

    asg_name = tags.get("aws:autoscaling:groupName")
    recent_activity_days = 0 if finding.get("state") == "running" else _parse_launch_days(
        finding.get("launch_time")
    )

    return {
        "resource_id": finding["instance_id"],
        "environment": _normalize_environment(env_raw),
        "business_critical": business_critical,
        "attached_to_load_balancer": "aws:elasticloadbalancing" in str(tags).lower()
        or bool(tags.get("elasticloadbalancing:targetGroupArn")),
        "member_of_autoscaling_group": bool(asg_name),
        "owner_exists": bool(owner),
        "recent_activity_days": recent_activity_days,
    }


def metadata_from_ebs(finding: dict[str, Any]) -> dict[str, Any]:
    """Build risk metadata row from an EBS scout finding."""
    return {
        "resource_id": finding["volume_id"],
        "environment": "development",
        "business_critical": False,
        "attached_to_load_balancer": False,
        "member_of_autoscaling_group": False,
        "owner_exists": False,
        "recent_activity_days": 999 if finding.get("is_unattached") else 30,
    }


class AWSInfrastructureMetadataLoader:
    """Load Scout-exported metadata for the Risk Assessor pipeline."""

    def __init__(self, metadata_path: Path = DEFAULT_METADATA_CSV) -> None:
        self._metadata_path = metadata_path

    def generate(self, resource_ids: list[str]) -> pd.DataFrame:
        if not self._metadata_path.exists():
            raise FileNotFoundError(
                f"AWS infrastructure metadata not found at {self._metadata_path}. "
                "Run agents/scout/export_resources.py first."
            )

        metadata = pd.read_csv(self._metadata_path)
        if "resource_id" not in metadata.columns:
            raise ValueError("Infrastructure metadata CSV is missing resource_id column.")

        filtered = metadata[metadata["resource_id"].isin(resource_ids)].copy()
        missing = set(resource_ids) - set(filtered["resource_id"].tolist())
        if missing:
            logger.warning(
                "Infrastructure metadata missing for %d resource(s); filling defaults.",
                len(missing),
            )
            defaults = pd.DataFrame(
                [
                    {
                        "resource_id": resource_id,
                        "environment": "development",
                        "business_critical": False,
                        "attached_to_load_balancer": False,
                        "member_of_autoscaling_group": False,
                        "owner_exists": False,
                        "recent_activity_days": 999,
                    }
                    for resource_id in sorted(missing)
                ]
            )
            filtered = pd.concat([filtered, defaults], ignore_index=True)

        for column in (
            "business_critical",
            "attached_to_load_balancer",
            "member_of_autoscaling_group",
            "owner_exists",
        ):
            if column in filtered.columns:
                filtered[column] = filtered[column].map(_to_bool)

        if "recent_activity_days" in filtered.columns:
            filtered["recent_activity_days"] = pd.to_numeric(
                filtered["recent_activity_days"], errors="coerce"
            ).fillna(999).astype(int)

        return filtered


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}
