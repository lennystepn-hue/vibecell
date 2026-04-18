from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


EXPECTED_TABLES = {
    "users", "workspaces", "workspace_members", "cli_devices", "audit_log",
    "magic_link_tokens", "projects", "active_project", "project_repos",
    "project_environments", "project_infra", "project_context", "project_links",
    "project_commands", "stack_items", "project_stack", "tags", "project_tags",
    "integrations", "workspace_keys",
}


async def test_all_20_tables_exist(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        def _tables(sync_conn):  # type: ignore[no-untyped-def]
            return set(inspect(sync_conn).get_table_names())

        tables = await conn.run_sync(_tables)

    missing = EXPECTED_TABLES - tables
    assert not missing, f"missing tables: {missing}"


async def test_projects_has_unique_workspace_slug(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        def _constraints(sync_conn):  # type: ignore[no-untyped-def]
            return inspect(sync_conn).get_unique_constraints("projects")

        uqs = await conn.run_sync(_constraints)

    names = {u["name"] for u in uqs}
    assert "uq_projects_workspace_slug" in names


async def test_projects_fts_gin_index_exists(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'projects' AND indexname = 'projects_fts'"
            )
        )
        rows = result.fetchall()

    assert len(rows) == 1, "expected projects_fts GIN index to exist"
