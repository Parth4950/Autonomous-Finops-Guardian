from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from backend.config.settings import auth_secret

PASSWORDS = PasswordHasher()
SESSION_SECONDS = 60 * 60 * 24 * 7


def hash_password(password: str) -> str:
    return PASSWORDS.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return PASSWORDS.verify(encoded, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(value: str) -> str:
    return hmac.new(auth_secret().encode(), value.encode(), hashlib.sha256).hexdigest()


def expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)
