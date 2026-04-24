"""Project CRUD + active-project tracking."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.ulid import new_ulid
from app.models import ActiveProject, Project, ProjectTag, Tag

_RESERVED_SLUGS: frozenset[str] = frozenset(
    {"api", "admin", "public", "app", "www", "import", "settings", "billing", "auth"}
)


async def list_projects(
    db: AsyncSession,
    *,
    workspace_id: str,
    status: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[Project], str | None]:
    """Return (items, next_cursor). Cursor is the last item's created_at ISO string."""
    stmt = select(Project).where(Project.workspace_id == workspace_id)
    if status is not None:
        stmt = stmt.where(Project.status == status)
    if tag is not None:
        stmt = stmt.join(ProjectTag, ProjectTag.project_id == Project.id).join(
            Tag, and_(Tag.id == ProjectTag.tag_id, Tag.workspace_id == workspace_id)
        ).where(Tag.name == tag)
    if q is not None:
        pattern = f"%{q}%"
        stmt = stmt.where(Project.name.ilike(pattern) | Project.pitch.ilike(pattern))
    if cursor is not None:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError as e:
            raise ValidationError(detail=f"invalid cursor: {e}") from e
        stmt = stmt.where(Project.created_at < cursor_dt)

    # Custom position first (user drag-order), then most-recent
    stmt = stmt.order_by(Project.position.asc(), Project.created_at.desc()).limit(limit + 1)
    rows = (await db.execute(stmt)).scalars().all()

    has_more = len(rows) > limit
    items = list(rows[:limit])
    next_cursor = items[-1].created_at.isoformat() if has_more and items else None
    return items, next_cursor


async def get_project(db: AsyncSession, *, workspace_id: str, slug: str) -> Project:
    result = await db.execute(
        select(Project).where(Project.workspace_id == workspace_id, Project.slug == slug)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("project", slug)
    return project


async def create_project(
    db: AsyncSession,
    *,
    workspace_id: str,
    slug: str,
    name: str,
    emoji: str | None = None,
    color: str | None = None,
    pitch: str | None = None,
    status: str = "building",
) -> Project:
    if slug in _RESERVED_SLUGS:
        raise ValidationError(detail=f"slug {slug!r} is reserved")

    existing = (await db.execute(
        select(Project.id).where(
            Project.workspace_id == workspace_id, Project.slug == slug
        )
    )).first()
    if existing is not None:
        raise ConflictError(detail=f"project slug {slug!r} already exists in this workspace")

    project = Project(
        id=new_ulid(),
        workspace_id=workspace_id,
        slug=slug,
        name=name,
        emoji=emoji,
        color=color,
        pitch=pitch,
        status=status,
    )
    db.add(project)
    await db.flush()
    return project


async def update_project(
    db: AsyncSession,
    *,
    project: Project,
    name: str | None = None,
    emoji: str | None = None,
    color: str | None = None,
    pitch: str | None = None,
    status: str | None = None,
    is_public: int | None = None,
) -> Project:
    if name is not None:
        project.name = name
    if emoji is not None:
        project.emoji = emoji
    if color is not None:
        project.color = color
    if pitch is not None:
        project.pitch = pitch
    if status is not None:
        project.status = status
        # archived_at tracks the archive timestamp; clear it when the user
        # un-archives the project so the UI no longer shows the "Archived"
        # badge after status changes to something else.
        if status == "archived":
            project.archived_at = datetime.now(UTC)
        else:
            project.archived_at = None
    if is_public is not None:
        project.is_public = is_public
    await db.flush()
    return project


async def delete_project(db: AsyncSession, *, project: Project) -> None:
    """Hard delete. Cascade removes all child rows (repos, links, etc.)."""
    await db.delete(project)
    await db.flush()


async def set_active_project(
    db: AsyncSession, *, workspace_id: str, user_id: str, project: Project,
) -> ActiveProject:
    existing = (await db.execute(
        select(ActiveProject).where(ActiveProject.workspace_id == workspace_id)
    )).scalar_one_or_none()
    now = datetime.now(UTC)
    if existing is None:
        row = ActiveProject(
            workspace_id=workspace_id,
            user_id=user_id,
            project_id=project.id,
            set_at=now,
        )
        db.add(row)
    else:
        existing.user_id = user_id
        existing.project_id = project.id
        existing.set_at = now
        row = existing
    await db.flush()
    return row
