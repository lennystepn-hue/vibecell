from datetime import UTC, datetime

from sqlalchemy import TIMESTAMP, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.ulid import new_ulid


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model."""


def ulid_pk() -> Mapped[str]:
    """Reusable ULID primary-key column factory."""
    return mapped_column(primary_key=True, default=new_ulid, index=False)


class TimestampMixin:
    """Mix in `created_at` + `updated_at` timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
