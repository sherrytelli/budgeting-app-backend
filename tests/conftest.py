"""Shared fixtures for the UI-contract test suite.

The suite runs from the host against the loopback-published Postgres port
(see ``docker-compose.yml``). ``DATABASE_URL`` is overridden through the
environment — the ``.env`` file is never mutated — *before* any ``app``
module is imported, because ``app.core.database`` builds its engine at
import time from the settings singleton.

Each session drops and recreates the dedicated ``test_budget_db`` database,
so the suite always starts from a pristine schema (``init_db`` →
``Base.metadata.create_all``, mirroring the Alembic-migrated models).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from dataclasses import dataclass

import asyncpg  # type: ignore[import-untyped]  # asyncpg ships no type stubs
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = "postgresql+asyncpg://budget_user:budget_secure_password@127.0.0.1:5432/test_budget_db"

# Must run before any app import: app.core.database reads DATABASE_URL at
# import time via the settings singleton.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.core import database  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402
from tests.helpers import AuthHeaders, login_headers, register_user, unique_email  # noqa: E402

_TEST_URL = make_url(TEST_DATABASE_URL)
if _TEST_URL.database != "test_budget_db":
    raise RuntimeError("contract tests refuse to run against a non-test database")

# NullPool: the bootstrap helpers run in their own event loops (asyncio.run),
# and a pooled asyncpg connection created on one loop must never be handed to
# another. NullPool gives every checkout a fresh, loop-local connection.
engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
test_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Patch the module globals get_db/init_db reference so every request and the
# schema bootstrap use the test engine instead of the .env-configured one.
database.engine = engine
database.async_session_maker = test_session_maker


@dataclass(frozen=True)
class ProvisionedUser:
    """A provisioned user plus the bearer headers for its JWT."""

    email: str
    password: str
    user_id: str
    headers: AuthHeaders


async def _recreate_test_database() -> None:
    """Drop and recreate the test database for a pristine schema each session."""
    assert _TEST_URL.username is not None
    assert _TEST_URL.password is not None
    admin = await asyncpg.connect(
        host=_TEST_URL.host,
        port=_TEST_URL.port or 5432,
        user=_TEST_URL.username,
        password=_TEST_URL.password,
        database="postgres",
    )
    try:
        await admin.execute('DROP DATABASE IF EXISTS "test_budget_db" WITH (FORCE)')
        await admin.execute('CREATE DATABASE "test_budget_db"')
    finally:
        await admin.close()


async def _create_schema() -> None:
    """Create every table, index, and constraint declared on the models."""
    await database.init_db()


async def _deactivate_user(email: str) -> None:
    """Flip ``is_active`` to False directly in the database."""
    async with test_session_maker() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.is_active = False
        await session.commit()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """Recreate test_budget_db and yield a TestClient bound to it.

    The client is a context manager so all requests share one portal event
    loop (Starlette creates a fresh loop per request otherwise).
    """
    asyncio.run(_recreate_test_database())
    asyncio.run(_create_schema())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def active_user(client: TestClient) -> ProvisionedUser:
    """Registered + logged-in active user with unique credentials."""
    email = unique_email("active")
    password = "Contract-Test-Passw0rd!"
    user_id = register_user(client, email, password)
    return ProvisionedUser(
        email=email,
        password=password,
        user_id=user_id,
        headers=login_headers(client, email, password),
    )


@pytest.fixture
def inactive_user(client: TestClient) -> ProvisionedUser:
    """Registered-but-deactivated user with a directly minted JWT.

    ``/auth/login`` rejects inactive accounts (403), so the token is minted
    with the same helper the app uses; ``/auth/me`` must still reject it (403).
    """
    email = unique_email("inactive")
    password = "Contract-Test-Passw0rd!"
    user_id = register_user(client, email, password)
    asyncio.run(_deactivate_user(email))
    token = create_access_token(user_id)
    return ProvisionedUser(
        email=email,
        password=password,
        user_id=user_id,
        headers={"Authorization": f"Bearer {token}"},
    )
