from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config.settings import database_connect_args, database_url
from backend.db.migrations import run_database_migrations

_migrated_urls: set[str] = set()


@lru_cache
def get_engine():
    url = database_url()
    connect_args = database_connect_args(url)
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def ensure_database_migrated() -> None:
    """Run Alembic migrations once per active DATABASE_URL against the runtime engine."""
    url = database_url()
    if url in _migrated_urls:
        return
    engine = get_engine()
    run_database_migrations(engine)
    _migrated_urls.add(url)


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db():
    ensure_database_migrated()
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
