from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from backend.config.settings import database_connect_args, database_url
from backend.db.base import Base
from backend.models.auth import User, UserSession  # noqa: F401
from backend.models.finops import (  # noqa: F401
    AWSAccount,
    Anomaly,
    Approval,
    ApprovalEvent,
    Execution,
    FinOpsReport,
    Forecast,
    Resource,
    Scan,
    ScanResourceSnapshot,
    ScanStage,
)

config = context.config
url = database_url()
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _execute_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
    if connection.in_transaction():
        connection.commit()


def run_migrations_online() -> None:
    provided_connection = config.attributes.get("connection")
    if provided_connection is not None:
        _execute_migrations(provided_connection)
        return

    runtime_url = database_url()
    connectable = create_engine(
        runtime_url,
        poolclass=pool.NullPool,
        connect_args=database_connect_args(runtime_url),
    )
    try:
        with connectable.connect() as connection:
            _execute_migrations(connection)
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
