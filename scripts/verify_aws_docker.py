"""Read-only AWS credential and API verification for the backend container.

Run with ``docker compose exec backend python /app/scripts/verify_aws_docker.py``.
This script does not start the FinOps pipeline or modify AWS resources.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from botocore.exceptions import BotoCoreError, ClientError

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.utils.aws_client import (  # noqa: E402
    AWSClientError,
    AWSClientHelper,
    AWSConfigurationError,
    load_aws_environment,
)


def report(name: str, passed: bool, detail: str) -> bool:
    print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
    return passed


def safe_error(exc: Exception) -> str:
    """Return a useful error category without echoing provider text/secrets."""
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        if code in {"ExpiredToken", "ExpiredTokenException", "TokenRefreshRequired"}:
            return "temporary credentials expired; restart the Learner Lab and refresh .env"
        if code in {"InvalidClientTokenId", "UnrecognizedClientException", "SignatureDoesNotMatch"}:
            return "credentials were rejected; verify the current Learner Lab credentials"
        if code in {"UnauthorizedOperation", "AccessDenied", "AccessDeniedException"}:
            return f"IAM denied the read-only request ({code})"
        if code == "InvalidInstanceID.NotFound":
            return f"AWS returned {code}"
        return f"AWS returned {code}"
    if isinstance(exc, AWSClientError):
        return "AWS client creation failed; verify credentials and region"
    if isinstance(exc, BotoCoreError):
        return "AWS SDK/network error; verify container network and region"
    if isinstance(exc, AWSConfigurationError):
        return "required AWS credential configuration is missing"
    if isinstance(exc, FileNotFoundError):
        return "project-root .env is unavailable in the container"
    return f"{type(exc).__name__}; details suppressed for credential safety"


def check(name: str, operation: Callable[[], object]) -> tuple[bool, object | None]:
    try:
        result = operation()
        return report(name, True, "request succeeded"), result
    except Exception as exc:  # Report each API independently, without secrets.
        report(name, False, safe_error(exc))
        return False, None


def main() -> int:
    try:
        load_aws_environment()
    except Exception as exc:
        report("project-root .env", False, safe_error(exc))
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_REGION"):
            report(key, False, "MISSING; .env could not be loaded")
        report("EXECUTION_MODE", os.getenv("EXECUTION_MODE", "simulation").lower() == "simulation", "must be simulation")
        return 1

    credentials_present = True
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_REGION"):
        present = bool(os.getenv(key, "").strip())
        report(key, present, "PRESENT" if present else "MISSING")
        if key != "AWS_SESSION_TOKEN" and not present:
            credentials_present = False

    mode_ok = os.getenv("EXECUTION_MODE", "simulation").strip().lower() == "simulation"
    report("EXECUTION_MODE", mode_ok, "simulation" if mode_ok else "not simulation")

    if not credentials_present or not mode_ok:
        return 1

    try:
        aws = AWSClientHelper()
        sts = aws.create_client("sts")
        identity = sts.get_caller_identity()
        report("STS GetCallerIdentity", True, f"account={identity['Account']} arn={identity['Arn']}")
    except Exception as exc:
        report("STS GetCallerIdentity", False, safe_error(exc))
        return 1

    _, instances = check(
        "EC2 DescribeInstances",
        lambda: aws.create_client("ec2").describe_instances(MaxResults=5),
    )
    _, volumes = check(
        "EC2 DescribeVolumes",
        lambda: aws.create_client("ec2").describe_volumes(MaxResults=5),
    )

    instance_id = None
    if instances is not None:
        instance_id = next(
            (item["InstanceId"] for reservation in instances.get("Reservations", [])
             for item in reservation.get("Instances", []) if item.get("InstanceId")),
            None,
        )
    # A syntactically valid dimension is sufficient when the account has no
    # instances; CloudWatch returns an empty datapoint list for an unreported ID.
    metric_instance_id = instance_id or "i-00000000000000000"
    end_time = datetime.now(timezone.utc)
    metric_ok, metric_result = check(
        "CloudWatch GetMetricStatistics",
        lambda: aws.create_client("cloudwatch").get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": metric_instance_id}],
            StartTime=end_time - timedelta(minutes=10),
            EndTime=end_time,
            Period=60,
            Statistics=["Average"],
            Unit="Percent",
        ),
    )
    if metric_ok and metric_result is not None:
        print(f"CloudWatch datapoints: {len(metric_result.get('Datapoints', []))}")

    return 0 if instances is not None and volumes is not None and metric_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
