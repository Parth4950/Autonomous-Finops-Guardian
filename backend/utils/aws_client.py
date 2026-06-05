"""Shared AWS client factory for Boto3 service connections."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import pip_system_certs  # noqa: F401 — use Windows certificate store for SSL
except ImportError:
    pass

import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"

_REQUIRED_AWS_ENV_VARS: tuple[str, ...] = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
)


@dataclass(frozen=True)
class AWSCredentials:
    """Validated AWS credential bundle."""

    access_key_id: str
    secret_access_key: str
    region: str


class AWSConfigurationError(ValueError):
    """Raised when required AWS environment variables are missing or invalid."""


class AWSClientError(RuntimeError):
    """Raised when Boto3 client creation or API calls fail."""


def load_aws_environment() -> None:
    """
    Load AWS variables from the project-root .env file.

    Raises:
        FileNotFoundError: If the .env file does not exist.
    """
    if not _ENV_FILE.exists():
        raise FileNotFoundError(
            f".env file not found at {_ENV_FILE}. "
            "Copy .env.example to .env and fill in your AWS credentials."
        )

    load_dotenv(_ENV_FILE, override=True)


def get_aws_credentials(region: str | None = None) -> AWSCredentials:
    """
    Load and validate AWS credentials from the environment.

    Args:
        region: Optional region override. Falls back to AWS_REGION env var,
            then ``ap-southeast-2`` as the project default.

    Returns:
        A validated AWSCredentials instance.

    Raises:
        AWSConfigurationError: If required variables are missing or blank.
    """
    load_aws_environment()

    missing = [
        name for name in _REQUIRED_AWS_ENV_VARS if not os.getenv(name, "").strip()
    ]
    if missing:
        raise AWSConfigurationError(
            f"Missing required AWS environment variables: {', '.join(missing)}"
        )

    resolved_region = (
        region
        or os.getenv("AWS_REGION", "ap-southeast-2").strip()
    ).lower()

    if not resolved_region:
        raise AWSConfigurationError("AWS region cannot be empty.")

    return AWSCredentials(
        access_key_id=os.environ["AWS_ACCESS_KEY_ID"].strip(),
        secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"].strip(),
        region=resolved_region,
    )


class AWSClientHelper:
    """
    Factory for authenticated Boto3 service clients.

    Loads credentials from .env and provides reusable client instances
    for AWS resource discovery across agents.
    """

    def __init__(self, region: str | None = None) -> None:
        """
        Initialize the helper with credentials from the environment.

        Args:
            region: Optional AWS region override for all clients.
        """
        self._credentials = get_aws_credentials(region=region)
        logger.info("AWS client helper initialized for region: %s", self.region)

    @property
    def region(self) -> str:
        """Return the configured AWS region."""
        return self._credentials.region

    def create_client(self, service_name: str) -> Any:
        """
        Create an authenticated Boto3 client for the given AWS service.

        Args:
            service_name: AWS service identifier (e.g. ``'ec2'``, ``'s3'``).

        Returns:
            A configured Boto3 client.

        Raises:
            AWSClientError: If credentials are invalid or client creation fails.
        """
        try:
            client = boto3.client(
                service_name,
                aws_access_key_id=self._credentials.access_key_id,
                aws_secret_access_key=self._credentials.secret_access_key,
                region_name=self._credentials.region,
            )
            logger.debug("Created Boto3 client for service: %s", service_name)
            return client

        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise AWSClientError(
                f"Invalid or incomplete AWS credentials: {exc}"
            ) from exc

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            error_message = exc.response.get("Error", {}).get("Message", str(exc))
            raise AWSClientError(
                f"Failed to create {service_name} client [{error_code}]: {error_message}"
            ) from exc

        except Exception as exc:
            raise AWSClientError(
                f"Unexpected error creating {service_name} client: {exc}"
            ) from exc
