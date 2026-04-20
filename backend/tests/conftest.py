from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """Prevent settings cache leakage across tests.

    Some tests mutate HANGAR_* env vars via monkeypatch and call
    `get_settings.cache_clear()` — but the cache populated during that test
    persists to the next test, leaking stale values (e.g. dev_mode=False
    making cookies Secure-only, breaking subsequent http:// client tests).
    Clearing before AND after each test gives deterministic per-test settings.
    """
    from app.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

# --- Set required env vars BEFORE any app module imports Settings. ---
# Safe defaults so `from app.core.config import get_settings` works at import time.
# HANGAR_DATABASE_URL is deliberately NOT set here; the `database_url` fixture
# decides it per-session (testcontainer vs HANGAR_TEST_DATABASE_URL override).
os.environ.setdefault("HANGAR_MASTER_KEY", "x" * 43)
os.environ.setdefault("HANGAR_REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HANGAR_RESEND_API_KEY", "test")
os.environ.setdefault("HANGAR_GITHUB_CLIENT_ID", "test")
os.environ.setdefault("HANGAR_GITHUB_CLIENT_SECRET", "test")
os.environ.setdefault("HANGAR_BASE_URL", "http://localhost:3000")
os.environ.setdefault("HANGAR_OAUTH_JWT_SECRET", "test_jwt_secret_" + "x" * 50)

# Lazy-import so tests that don't need DB don't pay testcontainers startup cost.
_pg_container: Any = None


def _start_testcontainer_postgres() -> str:
    """Start an ephemeral Postgres container; return its async DSN."""
    from testcontainers.postgres import PostgresContainer

    global _pg_container
    container = PostgresContainer("postgres:16-alpine", driver=None)
    try:
        container.start()
    except Exception:
        _pg_container = None
        raise
    _pg_container = container
    host = container.get_container_host_ip()
    port = container.get_exposed_port(5432)
    user = container.username
    password = container.password
    dbname = container.dbname
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"


# NOTE: No custom `event_loop` fixture — pytest-asyncio manages one per session
# via `asyncio_default_fixture_loop_scope = "session"` in pyproject.toml. The
# old explicit fixture conflicted with `command.upgrade(...)`'s internal
# `asyncio.run(...)` call (see `engine` fixture below for the workaround).


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def database_url() -> str:
    """Resolve which Postgres to use for this test session.

    Priority:
      1. HANGAR_TEST_DATABASE_URL — use directly (CI service, or already-running local instance)
      2. Otherwise, start a testcontainers Postgres 16 and use that.
    """
    override = os.environ.get("HANGAR_TEST_DATABASE_URL")
    if override:
        return override
    return _start_testcontainer_postgres()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    """Session-scoped async engine. Creates schema via alembic upgrade once;
    tests run in wrapping transactions that get rolled back at function scope."""
    from alembic.config import Config

    from alembic import command
    from app.core.config import get_settings
    from app.models.base import Base

    # Surface the chosen DB URL to both Alembic env.py and the app's Settings.
    os.environ["HANGAR_DATABASE_URL"] = database_url
    get_settings.cache_clear()

    eng = create_async_engine(database_url, echo=False, pool_pre_ping=True)

    # Drop everything including `alembic_version` — a plain `drop_all` only
    # removes tables in `Base.metadata`, leaving alembic_version behind from
    # a prior run so Alembic would skip migrations thinking we're already at
    # head. Nuking the schema is the simplest deterministic reset.
    from sqlalchemy import text
    async with eng.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

    alembic_root = Path(__file__).parent.parent
    cfg = Config(str(alembic_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(alembic_root / "alembic"))
    # Alembic's async env.py internally calls `asyncio.run(...)`, which cannot
    # be nested inside the pytest-asyncio event loop. Run it in a worker
    # thread so `asyncio.run` there is free to spin up its own loop.
    await asyncio.to_thread(command.upgrade, cfg, "head")
    # Silence unused-import warning while keeping Base in scope for future use.
    _ = Base

    yield eng
    await eng.dispose()
    if _pg_container is not None:
        _pg_container.stop()


@pytest_asyncio.fixture(loop_scope="session")
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


@pytest_asyncio.fixture
async def registered_oauth_client(session: AsyncSession):
    """Seed an OAuthClient row for authorize/grant/deny integration tests."""
    from datetime import datetime, timezone

    from app.core.ulid import new_ulid
    from app.oauth.models import OAuthClient

    row = OAuthClient(
        id=new_ulid(),
        client_id="dyn_" + new_ulid()[:16],
        client_name="Test Client",
        redirect_uris=["http://127.0.0.1:1/cb"],
        scope="vibecell:tools",
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()
    yield row


# ---------------------------------------------------------------------------
# Shared HTTP client fixtures (used by test_oauth_token.py, test_oauth_revoke.py)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Unauthenticated AsyncClient — for /oauth/token and /oauth/revoke calls."""
    from app.main import app
    from tests._auth_helpers import clear_db_override, override_db

    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c:
            yield c
    finally:
        clear_db_override()


@pytest_asyncio.fixture
async def authed_client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """AsyncClient signed in as the shared revoke/token test user."""
    from app.main import app
    from tests._auth_helpers import clear_db_override, override_db, sign_in

    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-revoke-test@example.com")
            yield c
    finally:
        clear_db_override()


@pytest_asyncio.fixture
async def user_workspace(session: AsyncSession, authed_client: AsyncClient):
    """Return the Workspace auto-created for the signed-in revoke test user."""
    from sqlalchemy import select

    from app.models import User, Workspace, WorkspaceMember

    user = (await session.execute(
        select(User).where(User.email == "oauth-revoke-test@example.com")
    )).scalar_one()

    ws = (await session.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .limit(1)
    )).scalar_one()
    return ws


@pytest_asyncio.fixture
async def issued_token_pair(authed_client, client, registered_oauth_client, user_workspace):
    """Drive authorize→grant→token flow and return {access_token, refresh_token, client_id}."""
    import base64
    import hashlib

    verifier = "v" + "a" * 42
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    cid = registered_oauth_client.client_id
    redirect = registered_oauth_client.redirect_uris[0]

    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri={redirect}"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=fix&scope=vibecell:tools",
        headers={"accept": "application/json"},
    )
    r = await authed_client.post(
        "/oauth/grant",
        json={"state": "fix", "workspace_id": user_workspace.id},
        follow_redirects=False,
    )
    code = r.headers["location"].split("code=")[1].split("&")[0]
    pair = (await client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
        "client_id": cid, "code_verifier": verifier,
    })).json()
    pair["client_id"] = cid
    return pair


@pytest_asyncio.fixture
async def mcp_client(client, issued_token_pair):
    client.headers.update({"Authorization": f"Bearer {issued_token_pair['access_token']}"})
    yield client
    client.headers.pop("Authorization", None)


@pytest_asyncio.fixture
async def user_workspace_with_active_project(session, user_workspace, authed_client):
    """Seed a 'vibecell' project + mark it active for the user."""
    from sqlalchemy import select

    from app.core.ulid import new_ulid
    from app.models import ActiveProject, Project, User

    user = (await session.execute(
        select(User).where(User.email == "oauth-revoke-test@example.com")
    )).scalar_one()

    proj = Project(
        id=new_ulid(),
        workspace_id=user_workspace.id,
        slug="vibecell",
        name="Vibecell",
        pitch="Test project for MCP",
        status="live",
        emoji="◈",
    )
    session.add(proj)
    await session.flush()

    # Mark active — ActiveProject PK is workspace_id; also requires user_id
    active = ActiveProject(
        workspace_id=user_workspace.id,
        user_id=user.id,
        project_id=proj.id,
    )
    session.add(active)
    await session.flush()

    yield {"workspace": user_workspace, "project": proj}
