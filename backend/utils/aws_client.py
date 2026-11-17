"""Shared AWS client factory for Boto3 service connections."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

try:
    import pip_system_certs  # noqa: F401 — use Windows certificate store for SSL
except ImportError:
    pass

import boto3
from botocore.exceptions import (
    BotoCoreError,
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
    """Validated AWS credential bundle with redacted string formatting."""

    access_key_id: str
    secret_access_key: str
    region: str
    session_token: str | None = None

    def __repr__(self) -> str:
        prefix = self.access_key_id[:4] if len(self.access_key_id) >= 4 else "***"
        return (
            f"AWSCredentials(access_key_id='{prefix}***', "
            f"secret_access_key='***REDACTED***', region='{self.region}', "
            f"has_session_token={self.session_token is not None})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class STSIdentity:
    """Verified AWS caller identity returned by STS GetCallerIdentity."""

    account_id: str
    arn: str
    user_id: str
    region: str


class AWSConfigurationError(ValueError):
    """Raised when required AWS environment variables are missing or invalid."""


class AWSClientError(RuntimeError):
    """Raised when Boto3 client creation or API calls fail."""


class AWSVerificationError(AWSClientError):
    """Raised when STS GetCallerIdentity verification fails, with a sanitized message."""

    def __init__(
        self,
        message: str,
        *,
        verification_status: Literal["invalid", "expired"] = "invalid",
    ) -> None:
        super().__init__(message)
        self.verification_status = verification_status


_EXPIRED_TOKEN_CODES = frozenset(
    {
        "ExpiredToken",
        "ExpiredTokenException",
        "TokenRefreshRequired",
        "RequestExpired",
    }
)
_INVALID_CREDENTIAL_CODES = frozenset(
    {
        "AuthFailure",
        "InvalidAccessKeyId",
        "InvalidClientTokenId",
        "InvalidToken",
        "MalformedToken",
        "SignatureDoesNotMatch",
        "UnrecognizedClientException",
    }
)
_ACCESS_DENIED_CODES = frozenset(
    {
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
    }
)
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{12,124}\b"),
    re.compile(r"(?i)(aws_secret_access_key|secret_access_key|aws_session_token|session_token)\s*[:=]\s*\S+"),
    re.compile(r"\b[A-Za-z0-9/+=]{40,}\b"),
)


def sanitize_aws_error_message(raw_error: str | Exception) -> str:
    """Return a user-safe error summary without exposing raw credentials or tokens."""
    if isinstance(raw_error, AWSVerificationError):
        return str(raw_error)
    if isinstance(raw_error, ClientError):
        code = str(raw_error.response.get("Error", {}).get("Code", "Unknown"))
        if code in _EXPIRED_TOKEN_CODES:
            return "AWS session token has expired. Refresh your temporary credentials and try again."
        if code in _INVALID_CREDENTIAL_CODES:
            return "AWS credentials were rejected. Verify your Access Key ID, Secret Access Key, and Session Token."
        if code in _ACCESS_DENIED_CODES:
            return f"AWS IAM denied the requested read-only operation ({code})."
        return f"AWS API request failed ({code})."
    if isinstance(raw_error, (NoCredentialsError, PartialCredentialsError)):
        return "AWS credentials are missing or incomplete."
    if isinstance(raw_error, BotoCoreError):
        return "Could not connect to AWS endpoint. Verify the configured region and network connectivity."

    text = str(raw_error).strip()
    if not text:
        return "Operation failed due to an unexpected AWS error."
    for code in _EXPIRED_TOKEN_CODES:
        if code in text:
            return "AWS session token has expired. Refresh your temporary credentials and try again."
    for code in _INVALID_CREDENTIAL_CODES:
        if code in text:
            return "AWS credentials were rejected. Verify your Access Key ID, Secret Access Key, and Session Token."
    for code in _ACCESS_DENIED_CODES:
        if code in text:
            return f"AWS IAM denied the requested read-only operation ({code})."

    sanitized = text
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


def load_aws_environment() -> None:
    """
    Load AWS variables from the project-root .env file without overwriting
    explicitly injected per-scan or process environment credentials.
    """
    if os.getenv("FINOPS_AWS_CREDENTIAL_SOURCE", "").strip().lower() == "account":
        return
    if _ENV_FILE.is_file():
        # Remove blank Compose interpolation placeholders before loading .env
        # with override=False so non-empty runtime/per-scan variables always win.
        for key in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_REGION",
        ):
            if key in os.environ and not os.environ[key].strip():
                os.environ.pop(key, None)
        load_dotenv(_ENV_FILE, override=False)


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
        session_token=os.getenv("AWS_SESSION_TOKEN", "").strip() or None,
    )


class AWSClientHelper:
    """
    Factory for authenticated Boto3 service clients.

    Loads credentials from .env and provides reusable client instances
    for AWS resource discovery across agents.
    """

    def __init__(
        self,
        region: str | None = None,
        credentials: AWSCredentials | None = None,
    ) -> None:
        """
        Initialize the helper with explicit credentials or environment fallback.

        Args:
            region: Optional AWS region override for all clients.
            credentials: Optional explicit AWSCredentials bundle.
        """
        if credentials is not None:
            resolved_region = (region or credentials.region or "ap-south-1").strip().lower()
            self._credentials = AWSCredentials(
                access_key_id=credentials.access_key_id.strip(),
                secret_access_key=credentials.secret_access_key.strip(),
                region=resolved_region,
                session_token=credentials.session_token.strip() if credentials.session_token else None,
            )
        else:
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
            client_options = {
                "aws_access_key_id": self._credentials.access_key_id,
                "aws_secret_access_key": self._credentials.secret_access_key,
                "region_name": self._credentials.region,
            }
            if self._credentials.session_token:
                client_options["aws_session_token"] = self._credentials.session_token
            client = boto3.client(service_name, **client_options)
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
                f"Unexpected error creating {service_name} client: {sanitize_aws_error_message(exc)}"
            ) from exc


def verify_aws_credentials(
    *,
    access_key_id: str,
    secret_access_key: str,
    region: str = "ap-south-1",
    session_token: str | None = None,
) -> STSIdentity:
    """Verify AWS credentials via STS GetCallerIdentity and return the caller's 12-digit Account ID and ARN."""
    cleaned_region = (region or "ap-south-1").strip().lower()
    if not cleaned_region:
        raise AWSVerificationError("AWS region cannot be empty.", verification_status="invalid")

    creds = AWSCredentials(
        access_key_id=access_key_id.strip(),
        secret_access_key=secret_access_key.strip(),
        region=cleaned_region,
        session_token=session_token.strip() if session_token and session_token.strip() else None,
    )
    try:
        sts_client = AWSClientHelper(region=cleaned_region, credentials=creds).create_client("sts")
        identity = sts_client.get_caller_identity()
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", "Unknown"))
        status_kind: Literal["invalid", "expired"] = (
            "expired" if code in _EXPIRED_TOKEN_CODES else "invalid"
        )
        raise AWSVerificationError(
            sanitize_aws_error_message(exc),
            verification_status=status_kind,
        ) from exc
    except (NoCredentialsError, PartialCredentialsError, BotoCoreError, AWSClientError) as exc:
        raise AWSVerificationError(
            sanitize_aws_error_message(exc),
            verification_status="invalid",
        ) from exc
    except Exception as exc:
        raise AWSVerificationError(
            sanitize_aws_error_message(exc),
            verification_status="invalid",
        ) from exc

    account_id = str(identity.get("Account") or "").strip()
    arn = str(identity.get("Arn") or "").strip()
    user_id = str(identity.get("UserId") or "").strip()
    if len(account_id) != 12 or not account_id.isdigit() or not arn:
        raise AWSVerificationError(
            "AWS STS returned an incomplete caller identity.",
            verification_status="invalid",
        )
    return STSIdentity(
        account_id=account_id,
        arn=arn,
        user_id=user_id,
        region=cleaned_region,
    )
