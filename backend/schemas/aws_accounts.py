"""Schemas for user-owned AWS account connections."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AWSAccountCreateRequest(BaseModel):
    """Payload to connect a user-owned AWS account."""

    display_name: str = Field(min_length=1, max_length=120, examples=["Learner Lab Sandbox"])
    access_key_id: str = Field(min_length=8, max_length=128, examples=["ASIAIOSFODNN7EXAMPLE"])
    secret_access_key: str = Field(min_length=1, max_length=256)
    session_token: str | None = Field(default=None, max_length=4096)
    default_region: str = Field(default="ap-south-1", min_length=2, max_length=64, examples=["us-east-1"])
    verify: bool = Field(
        default=True,
        description="Verify credentials immediately via STS GetCallerIdentity.",
    )


class AWSAccountUpdateRequest(BaseModel):
    """Payload to update metadata, region, or rotated credentials for an AWS account."""

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    default_region: str | None = Field(default=None, min_length=2, max_length=64)
    access_key_id: str | None = Field(default=None, min_length=8, max_length=128)
    secret_access_key: str | None = Field(default=None, min_length=1, max_length=256)
    session_token: str | None = Field(default=None, max_length=4096)
    clear_session_token: bool = Field(
        default=False,
        description="Clear an existing session token when switching to permanent IAM credentials.",
    )
    verify: bool = Field(
        default=True,
        description="Verify credentials via STS GetCallerIdentity when credentials are updated.",
    )


class AWSAccountVerifyRequest(BaseModel):
    """Optional region override when verifying an existing AWS account connection."""

    region: str | None = Field(default=None, min_length=2, max_length=64)


class AWSAccountResponse(BaseModel):
    """Safe, masked representation of a connected AWS account."""

    id: int
    user_id: int
    display_name: str
    aws_account_id: str | None = None
    arn: str | None = None
    default_region: str
    access_key_id_masked: str
    has_session_token: bool
    verification_status: str
    last_verified_at: str | None = None
    created_at: str
    updated_at: str
