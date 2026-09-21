"""Alembic migration environment, configured for the async SQLAlchemy engine."""

import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection

from alembic import context
from app import models  # noqa: F401 -- register domain models here as they are added
from app.core.config import Settings
from app.db.base import Base
from app.db.session import Database

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = Settings()

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection, emitting SQL to stdout."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        transactional_ddl=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure Alembic against an already-open connection and run migrations."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live async DB connection."""
    database = Database(settings.database_url)
    try:
        async with database.engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await database.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
