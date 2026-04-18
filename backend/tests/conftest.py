from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Lazy-import so tests that don't need DB don't pay testcontainers startup cost.
_pg_container: Any = None


def _start_testcontainer_postgres() -> str:
    """Start an ephemeral Postgres container; return its async DSN."""
    from testcontainers.postgres import PostgresContainer

    global _pg_container
    _pg_container = PostgresContainer("postgres:16-alpine", driver=None)
    _pg_container.start()
    host = _pg_container.get_container_host_ip()
    port = _pg_container.get_exposed_port(5432)
    user = _pg_container.username
    password = _pg_container.password
    dbname = _pg_container.dbname
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Session-scoped event loop so testcontainer + engine survive across tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def database_url() -> str:
    """Resolve which Postgres to use for this test session.

    Priority:
      1. HANGAR_TEST_DATABASE_URL — use directly (CI service, or already-running local instance)
      2. Otherwise, start a testcontainers Postgres 16 and use that.
    """
    override = os.environ.get("HANGAR_TEST_DATABASE_URL")
    if override:
        return override
    return _start_testcontainer_postgres()


@pytest_asyncio.fixture(scope="session")
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    """Session-scoped async engine. Creates schema once; tests run in wrapping transactions."""
    from app.models.base import Base

    eng = create_async_engine(database_url, echo=False, pool_pre_ping=True)

    # Apply all Alembic migrations to establish schema (incl. raw-SQL GIN index).
    import os
    from pathlib import Path

    from alembic.config import Config

    from alembic import command

    os.environ["HANGAR_DATABASE_URL"] = database_url
    os.environ.setdefault("HANGAR_MASTER_KEY", "x" * 43)
    os.environ.setdefault("HANGAR_REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("HANGAR_RESEND_API_KEY", "test")
    os.environ.setdefault("HANGAR_GITHUB_CLIENT_ID", "test")
    os.environ.setdefault("HANGAR_GITHUB_CLIENT_SECRET", "test")
    os.environ.setdefault("HANGAR_BASE_URL", "http://localhost:3000")

    # Drop everything first (in case of rerun)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parent.parent / "alembic"))
    # Ensure the env loads fresh with the right DB URL:
    command.upgrade(cfg, "head")

    yield eng
    await eng.dispose()
    if _pg_container is not None:
        _pg_container.stop()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Function-scoped session; rolls back the outer transaction at test end for isolation."""
    connection = await engine.connect()
    transaction = await connection.begin()
    factory = async_sessionmaker(bind=connection, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        try:
            yield s
        finally:
            await transaction.rollback()
            await connection.close()
