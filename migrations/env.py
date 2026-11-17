from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
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
config.set_main_option("sqlalchemy.url", database_url().replace("%", "%%"))
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    url = database_url()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=database_connect_args(url),
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
