"""Configuration module for environment and application settings."""

from backend.config.deployment import (
    aws_scan_enabled,
    cors_allow_origins,
    execution_mode,
    is_hosted_deployment,
)
from backend.config.settings import (
    CredentialsEncryptionError,
    auth_secret,
    credentials_encryption_key,
    database_connect_args,
    database_url,
)

__all__ = [
    "CredentialsEncryptionError",
    "auth_secret",
    "aws_scan_enabled",
    "cors_allow_origins",
    "credentials_encryption_key",
    "execution_mode",
    "database_url",
    "database_connect_args",
    "is_hosted_deployment",
]
