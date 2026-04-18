from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StackItem

pytestmark = pytest.mark.integration


async def test_stack_items_seeded(session: AsyncSession) -> None:
    result = await session.execute(select(StackItem))
    items = list(result.scalars())
    assert len(items) >= 40, f"expected ≥40 seeded stack items, got {len(items)}"

    slugs = {it.slug for it in items}
    # Spot-check canonical slugs
    for required in ["nextjs", "react", "vue", "fastapi", "postgres", "supabase",
                     "tailwind", "shadcn", "hetzner", "vercel", "stripe",
                     "anthropic", "openai", "claude", "gpt-4"]:
        assert required in slugs, f"expected seeded slug {required!r}"


async def test_stack_items_have_kind(session: AsyncSession) -> None:
    result = await session.execute(select(StackItem).where(StackItem.slug == "nextjs"))
    nextjs = result.scalar_one()
    assert nextjs.kind == "frontend"
    assert nextjs.name == "Next.js"
