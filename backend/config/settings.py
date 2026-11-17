"""Application settings loaded from environment variables."""

import base64
import binascii
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

# Load .env from project root before settings are instantiated.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Explicit deployment/test environment wins over local dotenv settings.
load_dotenv(_PROJECT_ROOT / ".env", override=False)


class CredentialsEncryptionError(RuntimeError):
    """Raised when CREDENTIALS_ENCRYPTION_KEY is missing or invalid."""


def database_url() -> str:
    """Return SQLAlchemy URL from DATABASE_URL, normalizing Supabase/Render/Railway schemes."""
    value = os.getenv("DATABASE_URL", "sqlite:///./finops-auth.db").strip() or "sqlite:///./finops-auth.db"
    if value.startswith("postgres://"):
        value = "postgresql+psycopg2://" + value[len("postgres://"):]
    elif value.startswith("postgresql://"):
        value = "postgresql+psycopg2://" + value[len("postgresql://"):]
    if value.startswith("postgresql+"):
        parsed = make_url(value)
        unsupported_params = {"pgbouncer", "connection_limit"}
        if unsupported_params.intersection(parsed.query):
            cleaned_query = {k: v for k, v in parsed.query.items() if k not in unsupported_params}
            value = parsed.set(query=cleaned_query).render_as_string(hide_password=False)
    return value


def database_connect_args(url: str | None = None) -> dict[str, object]:
    """Return driver arguments shared by runtime and Alembic connections."""
    value = url or database_url()
    if value.startswith("sqlite"):
        return {"check_same_thread": False}
    if value.startswith("postgresql+"):
        parsed = make_url(value)
        if "sslmode" not in parsed.query:
            local_host = parsed.host in {"localhost", "127.0.0.1", "::1"}
            return {"sslmode": "prefer" if local_host else "require"}
    return {}


def auth_secret() -> str:
    """Get the signing secret, requiring an explicit value in production."""
    value = os.getenv("AUTH_SECRET_KEY", "").strip()
    if value:
        return value
    if os.getenv("DEPLOYMENT_ENV", "").lower() in {"production", "hosted"} or os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER") == "true":
        raise RuntimeError("AUTH_SECRET_KEY must be configured in production.")
    # Development fallback is intentionally local-only and must not be deployed.
    return "local-development-only-change-before-deployment"


def credentials_encryption_key() -> bytes:
    """Load and validate the 32-byte key from CREDENTIALS_ENCRYPTION_KEY."""
    raw = os.getenv("CREDENTIALS_ENCRYPTION_KEY", "").strip()
    if not raw:
        raise CredentialsEncryptionError(
            "CREDENTIALS_ENCRYPTION_KEY must be configured in the environment."
        )
    try:
        padded = raw + "=" * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, binascii.Error) as exc:
        raise CredentialsEncryptionError(
            "CREDENTIALS_ENCRYPTION_KEY must be a valid URL-safe base64-encoded 32-byte key."
        ) from exc
    if len(decoded) != 32:
        raise CredentialsEncryptionError(
            "CREDENTIALS_ENCRYPTION_KEY must decode to exactly 32 bytes (256 bits)."
        )
    return decoded
