"""Application settings loaded from environment variables."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root before settings are instantiated.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

_REQUIRED_ENV_VARS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "DATABASE_URL",
)


@dataclass(frozen=True)
class Settings:
    """Validated application configuration sourced from environment variables."""

    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    database_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Load and validate settings from the current environment."""
        missing = [name for name in _REQUIRED_ENV_VARS if not os.getenv(name, "").strip()]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        aws_region = os.getenv("AWS_REGION", "ap-south-1").strip()
        if not aws_region:
            raise ValueError("AWS_REGION is required and cannot be empty.")

        return cls(
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"].strip(),
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"].strip(),
            aws_region=aws_region.lower(),
            database_url=os.environ["DATABASE_URL"].strip(),
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance for dependency injection."""
    return Settings.from_env()
