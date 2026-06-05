"""
AWS connectivity verification script for Autonomous FinOps Guardian.

Loads credentials from .env, creates a Boto3 EC2 client, and calls
describe_regions() to confirm authentication and API access.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

try:
    import pip_system_certs  # noqa: F401 — use Windows certificate store for SSL
except ImportError:
    pass

import boto3
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    PartialCredentialsError,
    SSLError,
)
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"

REQUIRED_ENV_VARS: tuple[str, ...] = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION",
)


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def load_environment() -> None:
    """Load variables from the project-root .env file into os.environ."""
    if not ENV_FILE.exists():
        raise FileNotFoundError(
            f".env file not found at {ENV_FILE}. "
            "Copy .env.example to .env and fill in your AWS credentials."
        )

    loaded = load_dotenv(ENV_FILE)
    if not loaded:
        logger.warning(".env file exists but no variables were loaded from it.")


def validate_required_env_vars() -> dict[str, str]:
    """
    Ensure all required AWS environment variables are present and non-empty.

    Returns:
        A dict mapping variable names to their stripped string values.

    Raises:
        ValueError: If one or more required variables are missing or blank.
    """
    missing: list[str] = []

    for var_name in REQUIRED_ENV_VARS:
        value = os.getenv(var_name, "").strip()
        if not value:
            missing.append(var_name)

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Set them in {ENV_FILE}."
        )

    return {
        "AWS_ACCESS_KEY_ID": os.environ["AWS_ACCESS_KEY_ID"].strip(),
        "AWS_SECRET_ACCESS_KEY": os.environ["AWS_SECRET_ACCESS_KEY"].strip(),
        "AWS_REGION": os.environ["AWS_REGION"].strip().lower(),
    }


# ---------------------------------------------------------------------------
# AWS client helpers
# ---------------------------------------------------------------------------


def create_ec2_client(
    access_key_id: str,
    secret_access_key: str,
    region: str,
) -> Any:
    """
    Build and return a Boto3 EC2 client using explicit credentials.

    Args:
        access_key_id: IAM user access key ID.
        secret_access_key: IAM user secret access key.
        region: AWS region name (e.g. 'ap-south-1').

    Returns:
        A configured boto3 EC2 client instance.
    """
    logger.info("Creating EC2 client for region: %s", region)

    return boto3.client(
        "ec2",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region,
    )


def fetch_available_regions(ec2_client: Any) -> list[str]:
    """
    Call describe_regions() and return a sorted list of region names.

    Args:
        ec2_client: An authenticated Boto3 EC2 client.

    Returns:
        Sorted list of enabled AWS region identifiers.

    Raises:
        ClientError: If the AWS API returns an error response.
        EndpointConnectionError: If the endpoint cannot be reached.
    """
    logger.info("Calling ec2:DescribeRegions to verify connectivity...")

    response = ec2_client.describe_regions(AllRegions=False)
    regions = sorted(
        region["RegionName"] for region in response.get("Regions", [])
    )

    return regions


def print_regions(regions: list[str]) -> None:
    """Print all available AWS regions to stdout."""
    print("\nAvailable AWS regions:")
    print("-" * 40)
    for region in regions:
        print(f"  • {region}")
    print("-" * 40)
    print(f"Total: {len(regions)} regions\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """
    Run the AWS connectivity verification workflow.

    Returns:
        0 on success, 1 on failure.
    """
    try:
        load_environment()
        credentials = validate_required_env_vars()

        ec2_client = create_ec2_client(
            access_key_id=credentials["AWS_ACCESS_KEY_ID"],
            secret_access_key=credentials["AWS_SECRET_ACCESS_KEY"],
            region=credentials["AWS_REGION"],
        )

        regions = fetch_available_regions(ec2_client)

        print("\n✅ AWS authentication successful!")
        print_regions(regions)

        logger.info("Connectivity check completed successfully.")
        return 0

    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    except (NoCredentialsError, PartialCredentialsError) as exc:
        logger.error("Invalid or incomplete AWS credentials: %s", exc)
        return 1

    except EndpointConnectionError as exc:
        logger.error("Connection error — could not reach AWS endpoint: %s", exc)
        return 1

    except SSLError as exc:
        logger.error(
            "SSL error — could not verify AWS endpoint certificate: %s. "
            "Ensure your system trust store is up to date or check proxy/firewall settings.",
            exc,
        )
        return 1

    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        error_message = exc.response.get("Error", {}).get("Message", str(exc))
        if error_code in ("AuthFailure", "InvalidClientTokenId", "SignatureDoesNotMatch"):
            logger.error(
                "AWS API error [%s]: %s. "
                "Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env file.",
                error_code,
                error_message,
            )
        else:
            logger.error("AWS API error [%s]: %s", error_code, error_message)
        return 1

    except Exception as exc:
        logger.exception("Unexpected error during AWS connectivity check: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
