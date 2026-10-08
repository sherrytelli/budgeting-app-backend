"""Alembic environment configuration for async SQLAlchemy migrations."""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from dotenv import load_dotenv

# Ensure the project root is on the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.models.base import Base  # noqa: E402
from app.models.budget import MonthlyBudget  # noqa: E402
from app.models.category import DailyCategory  # noqa: E402
from app.models.expense import Expense  # noqa: E402
from app.models.user import User  # noqa: E402

load_dotenv()

# Import the Base's metadata for autogenerate
target_metadata = Base.metadata

# Load configuration from alembic.ini
config = context.config

# Override the sqlalchemy.url from the DATABASE_URL environment variable
# This allows the same alembic.ini to work across environments
database_url = os.environ.get("ALEMBIC_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL statements against a URL without connecting to the database.
    Useful for previewing migrations or running them in environments where
    the database is not directly accessible.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    """Run the actual migrations against the database connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine.

    This is the preferred mode for async SQLAlchemy setups.
    It creates an async engine, connects, and runs migrations
    within a transaction.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async support.

    In async mode, we wrap the migration execution in an asyncio event loop.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
