"""Federated FTS search across projects/sessions/decisions/ideas/notes.

Runs 5 parallel `to_tsvector + plainto_tsquery + ts_rank_cd` queries,
each scoped to the active workspace, returns the top-N globally by rank.

Uses `plainto_tsquery('english', …)` which is forgiving — it auto-escapes
punctuation and spaces.  `ts_headline` renders a highlighted snippet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class SearchHit:
    entity: str
    entity_id: str
    project_slug: str | None
    project_id: str | None
    title: str | None
    snippet: str
    rank: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "entity_id": self.entity_id,
            "project_slug": self.project_slug,
            "project_id": self.project_id,
            "title": self.title,
            "snippet": self.snippet,
            "rank": self.rank,
        }


_QUERIES: dict[str, str] = {
    "project": """
        SELECT
            p.id AS entity_id,
            p.slug AS project_slug,
            p.id AS project_id,
            p.name AS title,
            ts_headline(
                'english',
                coalesce(p.name, '') || ' ' || coalesce(p.pitch, ''),
                plainto_tsquery('english', :q),
                'MaxFragments=1,MaxWords=25,MinWords=5'
            ) AS snippet,
            ts_rank_cd(
                to_tsvector('english', coalesce(p.name, '') || ' ' || coalesce(p.pitch, '')),
                plainto_tsquery('english', :q)
            ) AS rank
        FROM projects p
        WHERE p.workspace_id = :ws
          AND to_tsvector('english', coalesce(p.name, '') || ' ' || coalesce(p.pitch, ''))
              @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC
        LIMIT :per
    """,
    "session": """
        SELECT
            s.id AS entity_id,
            p.slug AS project_slug,
            p.id AS project_id,
            substr(coalesce(s.summary, ''), 1, 80) AS title,
            ts_headline(
                'english',
                coalesce(s.summary, '') || ' ' || coalesce(s.next_step, ''),
                plainto_tsquery('english', :q),
                'MaxFragments=1,MaxWords=25,MinWords=5'
            ) AS snippet,
            ts_rank_cd(
                to_tsvector('english', coalesce(s.summary, '') || ' ' || coalesce(s.next_step, '')),
                plainto_tsquery('english', :q)
            ) AS rank
        FROM sessions s
        JOIN projects p ON p.id = s.project_id
        WHERE p.workspace_id = :ws
          AND to_tsvector('english', coalesce(s.summary, '') || ' ' || coalesce(s.next_step, ''))
              @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC
        LIMIT :per
    """,
    "decision": """
        SELECT
            d.id AS entity_id,
            p.slug AS project_slug,
            p.id AS project_id,
            d.title AS title,
            ts_headline(
                'english',
                d.title || ' ' || coalesce(d.decision, '') || ' ' || coalesce(d.context, ''),
                plainto_tsquery('english', :q),
                'MaxFragments=1,MaxWords=25,MinWords=5'
            ) AS snippet,
            ts_rank_cd(
                to_tsvector('english', d.title || ' ' || coalesce(d.decision, '') || ' ' || coalesce(d.context, '')),
                plainto_tsquery('english', :q)
            ) AS rank
        FROM decisions d
        JOIN projects p ON p.id = d.project_id
        WHERE p.workspace_id = :ws
          AND to_tsvector('english', d.title || ' ' || coalesce(d.decision, '') || ' ' || coalesce(d.context, ''))
              @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC
        LIMIT :per
    """,
    "idea": """
        SELECT
            i.id AS entity_id,
            p.slug AS project_slug,
            i.project_id AS project_id,
            substr(i.body, 1, 80) AS title,
            ts_headline(
                'english', i.body,
                plainto_tsquery('english', :q),
                'MaxFragments=1,MaxWords=25,MinWords=5'
            ) AS snippet,
            ts_rank_cd(
                to_tsvector('english', i.body),
                plainto_tsquery('english', :q)
            ) AS rank
        FROM ideas i
        LEFT JOIN projects p ON p.id = i.project_id
        WHERE i.workspace_id = :ws
          AND to_tsvector('english', i.body) @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC
        LIMIT :per
    """,
    "note": """
        SELECT
            p.id AS entity_id,
            p.slug AS project_slug,
            p.id AS project_id,
            p.name AS title,
            ts_headline(
                'english', n.markdown,
                plainto_tsquery('english', :q),
                'MaxFragments=1,MaxWords=25,MinWords=5'
            ) AS snippet,
            ts_rank_cd(
                to_tsvector('english', n.markdown),
                plainto_tsquery('english', :q)
            ) AS rank
        FROM notes n
        JOIN projects p ON p.id = n.project_id
        WHERE p.workspace_id = :ws
          AND to_tsvector('english', n.markdown) @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC
        LIMIT :per
    """,
}


async def union_search(
    db: AsyncSession,
    *,
    workspace_id: str,
    query: str,
    limit: int = 50,
    entity_filter: str | None = None,
) -> list[SearchHit]:
    """Return up to `limit` hits ranked by FTS relevance across all entities.

    `entity_filter` narrows to a single entity kind; otherwise all five
    run and results merge by rank.
    """
    if not query.strip():
        return []

    entities = (
        [entity_filter] if entity_filter is not None else list(_QUERIES.keys())
    )
    entities = [e for e in entities if e in _QUERIES]

    # Each sub-query returns at most `limit` rows; the final merge cuts at `limit`.
    per_query_cap = limit

    hits: list[SearchHit] = []
    for entity in entities:
        sql = text(_QUERIES[entity])
        rows = (await db.execute(
            sql, {"ws": workspace_id, "q": query, "per": per_query_cap}
        )).mappings().all()
        for row in rows:
            hits.append(
                SearchHit(
                    entity=entity,
                    entity_id=row["entity_id"],
                    project_slug=row["project_slug"],
                    project_id=row["project_id"],
                    title=row["title"],
                    snippet=row["snippet"] or "",
                    rank=float(row["rank"]),
                )
            )

    hits.sort(key=lambda h: h.rank, reverse=True)
    return hits[:limit]
