"""User-owned AWS account management and STS verification service."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.finops import AWSAccount
from backend.schemas.aws_accounts import (
    AWSAccountCreateRequest,
    AWSAccountResponse,
    AWSAccountUpdateRequest,
)
from backend.utils.aws_client import (
    AWSVerificationError,
    STSIdentity,
    verify_aws_credentials,
)
from backend.utils.credential_encryption import (
    create_user_aws_account,
    get_user_aws_account,
    list_user_aws_accounts,
    serialize_aws_account,
)

_REGION_PATTERN = re.compile(r"^[a-z]{2}(-[a-z]+)+-\d+$")


class AWSAccountConflictError(ValueError):
    """Raised when a user already has an AWS account with the same display name."""


def _validate_region(region: str) -> str:
    cleaned = region.strip().lower()
    if not _REGION_PATTERN.match(cleaned):
        raise ValueError(f"Invalid AWS region format: '{cleaned}'. Expected format like 'ap-south-1' or 'us-east-1'.")
    return cleaned


class AWSAccountService:
    """Manage user-owned AWS account connections with encrypted credential storage."""

    def __init__(
        self,
        verifier: Callable[..., STSIdentity] = verify_aws_credentials,
    ) -> None:
        self._verifier = verifier

    def list_accounts(self, db: Session, user_id: int) -> list[AWSAccountResponse]:
        rows = list_user_aws_accounts(db, user_id=user_id)
        return [AWSAccountResponse.model_validate(serialize_aws_account(row)) for row in rows]

    def get_account(self, db: Session, user_id: int, account_id: int) -> AWSAccountResponse:
        row = get_user_aws_account(db, user_id=user_id, account_id=account_id)
        if row is None:
            raise LookupError("AWS account not found.")
        return AWSAccountResponse.model_validate(serialize_aws_account(row))

    def connect_account(
        self,
        db: Session,
        user_id: int,
        payload: AWSAccountCreateRequest,
    ) -> AWSAccountResponse:
        display_name = payload.display_name.strip()
        if not display_name:
            raise ValueError("Display name cannot be empty.")
        region = _validate_region(payload.default_region)

        existing = db.scalar(
            select(AWSAccount.id).where(
                AWSAccount.user_id == user_id,
                func.lower(AWSAccount.display_name) == display_name.lower(),
            )
        )
        if existing is not None:
            raise AWSAccountConflictError("An AWS account with this display name already exists.")

        aws_account_id: str | None = None
        arn: str | None = None
        verification_status = "unverified"
        last_verified_at: datetime | None = None

        if payload.verify:
            identity = self._verifier(
                access_key_id=payload.access_key_id,
                secret_access_key=payload.secret_access_key,
                region=region,
                session_token=payload.session_token,
            )
            aws_account_id = identity.account_id
            arn = identity.arn
            verification_status = "verified"
            last_verified_at = datetime.now(timezone.utc)

        account = create_user_aws_account(
            db,
            user_id=user_id,
            display_name=display_name,
            access_key_id=payload.access_key_id,
            secret_access_key=payload.secret_access_key,
            session_token=payload.session_token,
            default_region=region,
            aws_account_id=aws_account_id,
            arn=arn,
            verification_status=verification_status,
        )
        account.last_verified_at = last_verified_at

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise AWSAccountConflictError("An AWS account with this display name already exists.") from exc

        db.refresh(account)
        return AWSAccountResponse.model_validate(serialize_aws_account(account))

    def verify_account(
        self,
        db: Session,
        user_id: int,
        account_id: int,
        region: str | None = None,
    ) -> AWSAccountResponse:
        account = db.scalar(
            select(AWSAccount)
            .where(AWSAccount.id == account_id, AWSAccount.user_id == user_id)
            .with_for_update()
        )
        if account is None:
            raise LookupError("AWS account not found.")

        target_region = _validate_region(region) if region else account.default_region
        decrypted = account.decrypt_credentials(requesting_user_id=user_id)
        now = datetime.now(timezone.utc)

        try:
            identity = self._verifier(
                access_key_id=decrypted.access_key_id,
                secret_access_key=decrypted.secret_access_key,
                region=target_region,
                session_token=decrypted.session_token,
            )
        except AWSVerificationError as exc:
            account.verification_status = exc.verification_status
            account.updated_at = now
            db.commit()
            raise

        account.aws_account_id = identity.account_id
        account.arn = identity.arn
        account.verification_status = "verified"
        account.last_verified_at = now
        account.updated_at = now
        db.commit()
        db.refresh(account)
        return AWSAccountResponse.model_validate(serialize_aws_account(account))

    def update_account(
        self,
        db: Session,
        user_id: int,
        account_id: int,
        payload: AWSAccountUpdateRequest,
    ) -> AWSAccountResponse:
        account = db.scalar(
            select(AWSAccount)
            .where(AWSAccount.id == account_id, AWSAccount.user_id == user_id)
            .with_for_update()
        )
        if account is None:
            raise LookupError("AWS account not found.")

        if payload.display_name is not None:
            new_name = payload.display_name.strip()
            if not new_name:
                raise ValueError("Display name cannot be empty.")
            conflict = db.scalar(
                select(AWSAccount.id).where(
                    AWSAccount.user_id == user_id,
                    func.lower(AWSAccount.display_name) == new_name.lower(),
                    AWSAccount.id != account_id,
                )
            )
            if conflict is not None:
                raise AWSAccountConflictError("An AWS account with this display name already exists.")
            account.display_name = new_name

        if payload.default_region is not None:
            account.default_region = _validate_region(payload.default_region)

        has_new_key = payload.access_key_id is not None
        has_new_secret = payload.secret_access_key is not None
        if has_new_key != has_new_secret:
            raise ValueError("Both access_key_id and secret_access_key must be provided when updating credentials.")

        credentials_changed = False
        if has_new_key and has_new_secret:
            effective_token = None if payload.clear_session_token else payload.session_token
            account.set_credentials(
                access_key_id=payload.access_key_id or "",
                secret_access_key=payload.secret_access_key or "",
                session_token=effective_token,
            )
            credentials_changed = True
        elif payload.session_token is not None or payload.clear_session_token:
            current = account.decrypt_credentials(requesting_user_id=user_id)
            effective_token = None if payload.clear_session_token else payload.session_token
            account.set_credentials(
                access_key_id=current.access_key_id,
                secret_access_key=current.secret_access_key,
                session_token=effective_token,
            )
            credentials_changed = True

        now = datetime.now(timezone.utc)
        if credentials_changed:
            if payload.verify:
                decrypted = account.decrypt_credentials(requesting_user_id=user_id)
                identity = self._verifier(
                    access_key_id=decrypted.access_key_id,
                    secret_access_key=decrypted.secret_access_key,
                    region=account.default_region,
                    session_token=decrypted.session_token,
                )
                account.aws_account_id = identity.account_id
                account.arn = identity.arn
                account.verification_status = "verified"
                account.last_verified_at = now
            else:
                account.verification_status = "unverified"

        account.updated_at = now
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise AWSAccountConflictError("An AWS account with this display name already exists.") from exc

        db.refresh(account)
        return AWSAccountResponse.model_validate(serialize_aws_account(account))

    def disconnect_account(self, db: Session, user_id: int, account_id: int) -> None:
        account = db.scalar(
            select(AWSAccount).where(AWSAccount.id == account_id, AWSAccount.user_id == user_id)
        )
        if account is None:
            raise LookupError("AWS account not found.")
        db.delete(account)
        db.commit()
