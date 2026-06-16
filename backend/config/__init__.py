"""Configuration module for environment and application settings."""

from backend.config.deployment import (
    aws_scan_enabled,
    cors_allow_origins,
    execution_mode,
    is_hosted_deployment,
)
from backend.config.settings import Settings, get_settings

__all__ = [
    "Settings",
    "aws_scan_enabled",
    "cors_allow_origins",
    "execution_mode",
    "get_settings",
    "is_hosted_deployment",
]
