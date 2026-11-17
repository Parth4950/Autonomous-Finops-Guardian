"""Authenticated encryption, masking, and user-isolated storage helpers for AWS credentials."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import json
import secrets
from typing import TYPE_CHECKING, Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config.settings import CredentialsEncryptionError, credentials_encryption_key

if TYPE_CHECKING:
    from backend.models.finops import AWSAccount

ENVELOPE_VERSION = "v1"
NONCE_BYTES = 12


class CredentialTamperError(ValueError):
    """Raised when encrypted AWS credentials fail integrity, format, or ownership verification."""


@dataclass(frozen=True)
class StoredAWSCredentials:
    """Decrypted AWS credential bundle with redacted string/repr formatting."""

    access_key_id: str
    secret_access_key: str
    session_token: str | None = None

    def __repr__(self) -> str:
        masked = mask_access_key_id(self.access_key_id) if len(self.access_key_id) >= 8 else "***"
        has_token = self.session_token is not None
        return (
            f"StoredAWSCredentials(access_key_id='{masked}', "
            f"secret_access_key='***REDACTED***', has_session_token={has_token})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def generate_encryption_key() -> str:
    """Generate a URL-safe base64-encoded 32-byte key suitable for CREDENTIALS_ENCRYPTION_KEY."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def mask_access_key_id(access_key_id: str) -> str:
    """Return a masked AWS access key ID (e.g. AKIA************MPLE)."""
    if not isinstance(access_key_id, str):
        raise ValueError("access_key_id must be a string.")
    cleaned = access_key_id.strip()
    if len(cleaned) < 8 or len(cleaned) > 128:
        raise ValueError("access_key_id must be between 8 and 128 characters.")
    if not cleaned.isalnum():
        raise ValueError("access_key_id must contain only alphanumeric characters.")
    middle_len = max(4, len(cleaned) - 8)
    return f"{cleaned[:4]}{'*' * middle_len}{cleaned[-4:]}"


def _build_aad(user_id: int | None) -> bytes:
    if user_id is not None:
        if user_id <= 0:
            raise ValueError("user_id must be a positive integer.")
        return f"finops-aws-account:{ENVELOPE_VERSION}:user:{user_id}".encode("utf-8")
    return f"finops-aws-account:{ENVELOPE_VERSION}".encode("utf-8")


def encrypt_aws_credentials(
    *,
    access_key_id: str,
    secret_access_key: str,
    session_token: str | None = None,
    user_id: int | None = None,
) -> str:
    """Encrypt AWS credentials with AES-256-GCM bound to the owning user_id."""
    key = credentials_encryption_key()
    cleaned_key_id = access_key_id.strip() if isinstance(access_key_id, str) else ""
    cleaned_secret = secret_access_key.strip() if isinstance(secret_access_key, str) else ""
    cleaned_token = session_token.strip() if isinstance(session_token, str) and session_token.strip() else None

    # Validate access key format before encrypting
    mask_access_key_id(cleaned_key_id)
    if not cleaned_secret:
        raise ValueError("secret_access_key cannot be empty.")

    aad = _build_aad(user_id)
    payload = json.dumps(
        {
            "access_key_id": cleaned_key_id,
            "secret_access_key": cleaned_secret,
            "session_token": cleaned_token,
            "user_id": user_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, payload, aad)
    nonce_b64 = base64.urlsafe_b64encode(nonce).decode("ascii")
    cipher_b64 = base64.urlsafe_b64encode(ciphertext).decode("ascii")
    return f"{ENVELOPE_VERSION}.{nonce_b64}.{cipher_b64}"


def decrypt_aws_credentials(
    encrypted_payload: str,
    *,
    user_id: int | None = None,
) -> StoredAWSCredentials:
    """Decrypt and verify an AES-256-GCM AWS credential envelope."""
    key = credentials_encryption_key()
    if not isinstance(encrypted_payload, str) or not encrypted_payload.strip():
        raise CredentialTamperError("Encrypted credential payload is empty or invalid.")

    parts = encrypted_payload.strip().split(".")
    if len(parts) != 3 or parts[0] != ENVELOPE_VERSION or not parts[1] or not parts[2]:
        raise CredentialTamperError("Encrypted credential envelope format is invalid.")

    try:
        nonce = base64.urlsafe_b64decode(parts[1].encode("ascii"))
        ciphertext = base64.urlsafe_b64decode(parts[2].encode("ascii"))
    except (ValueError, binascii.Error) as exc:
        raise CredentialTamperError("Encrypted credential envelope encoding is corrupted.") from exc

    if (
        base64.urlsafe_b64encode(nonce).decode("ascii") != parts[1]
        or base64.urlsafe_b64encode(ciphertext).decode("ascii") != parts[2]
    ):
        raise CredentialTamperError("Encrypted credential envelope encoding is non-canonical or tampered.")

    if len(nonce) != NONCE_BYTES or len(ciphertext) <= 16:
        raise CredentialTamperError("Encrypted credential envelope length is invalid.")

    aad = _build_aad(user_id)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise CredentialTamperError(
            "Credential authentication failed: ciphertext was tampered with, key is wrong, or owner mismatched."
        ) from exc

    try:
        data = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CredentialTamperError("Decrypted credential payload is malformed.") from exc

    if not isinstance(data, dict) or data.get("user_id") != user_id:
        raise CredentialTamperError("Credential ownership verification failed.")

    access_key_id = data.get("access_key_id")
    secret_access_key = data.get("secret_access_key")
    session_token = data.get("session_token")
    if not isinstance(access_key_id, str) or not isinstance(secret_access_key, str) or not secret_access_key:
        raise CredentialTamperError("Decrypted credential fields are invalid.")
    if session_token is not None and not isinstance(session_token, str):
        raise CredentialTamperError("Decrypted session token field is invalid.")

    return StoredAWSCredentials(
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        session_token=session_token,
    )


def serialize_aws_account(account: AWSAccount) -> dict[str, Any]:
    """Return a safe, masked dictionary representation of an AWSAccount without secrets."""
    return {
        "id": account.id,
        "user_id": account.user_id,
        "display_name": account.display_name,
        "aws_account_id": account.aws_account_id,
        "arn": account.arn,
        "default_region": account.default_region,
        "access_key_id_masked": account.access_key_id_masked,
        "has_session_token": bool(account.has_session_token),
        "verification_status": account.verification_status,
        "last_verified_at": account.last_verified_at.isoformat() if account.last_verified_at else None,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }


def create_user_aws_account(
    db: Session,
    *,
    user_id: int,
    display_name: str,
    access_key_id: str,
    secret_access_key: str,
    session_token: str | None = None,
    default_region: str = "ap-south-1",
    aws_account_id: str | None = None,
    arn: str | None = None,
    verification_status: str = "unverified",
) -> AWSAccount:
    """Create a user-owned AWSAccount with masked key ID and AES-GCM encrypted secrets."""
    from backend.models.finops import AWSAccount

    if user_id <= 0:
        raise ValueError("user_id must be a positive integer.")
    cleaned_name = display_name.strip()
    cleaned_region = default_region.strip().lower()
    if not cleaned_name:
        raise ValueError("display_name cannot be empty.")
    if not cleaned_region:
        raise ValueError("default_region cannot be empty.")

    masked_key = mask_access_key_id(access_key_id)
    cleaned_token = session_token.strip() if isinstance(session_token, str) and session_token.strip() else None
    ciphertext = encrypt_aws_credentials(
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        session_token=cleaned_token,
        user_id=user_id,
    )

    account = AWSAccount(
        user_id=user_id,
        display_name=cleaned_name,
        aws_account_id=aws_account_id,
        arn=arn,
        default_region=cleaned_region,
        access_key_id_masked=masked_key,
        encrypted_credentials=ciphertext,
        has_session_token=cleaned_token is not None,
        verification_status=verification_status,
    )
    db.add(account)
    return account


def get_user_aws_account(db: Session, *, user_id: int, account_id: int) -> AWSAccount | None:
    """Fetch a single AWSAccount only when owned by the given user_id."""
    from backend.models.finops import AWSAccount

    return db.scalar(
        select(AWSAccount).where(AWSAccount.id == account_id, AWSAccount.user_id == user_id)
    )


def list_user_aws_accounts(db: Session, *, user_id: int) -> list[AWSAccount]:
    """List all AWSAccount rows owned by the given user_id."""
    from backend.models.finops import AWSAccount

    return list(
        db.scalars(
            select(AWSAccount)
            .where(AWSAccount.user_id == user_id)
            .order_by(AWSAccount.created_at.desc(), AWSAccount.id.desc())
        ).all()
    )


__all__ = [
    "CredentialsEncryptionError",
    "CredentialTamperError",
    "StoredAWSCredentials",
    "create_user_aws_account",
    "decrypt_aws_credentials",
    "encrypt_aws_credentials",
    "generate_encryption_key",
    "get_user_aws_account",
    "list_user_aws_accounts",
    "mask_access_key_id",
    "serialize_aws_account",
]
