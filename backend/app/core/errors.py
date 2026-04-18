from __future__ import annotations

from typing import Any


class HangarError(Exception):
    """Base exception mapped to RFC 7807 Problem+JSON by FastAPI handler."""

    def __init__(
        self,
        *,
        title: str,
        status: int,
        type_: str,
        detail: str | None = None,
        extras: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail or title)
        self.title = title
        self.status = status
        self.type = type_
        self.detail = detail
        self.extras = extras or {}

    def to_problem(self) -> dict[str, Any]:
        problem: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
        }
        if self.detail is not None:
            problem["detail"] = self.detail
        problem.update(self.extras)
        return problem


class NotFoundError(HangarError):
    def __init__(self, entity: str, identifier: str) -> None:
        super().__init__(
            title="Not Found",
            status=404,
            type_="/errors/not-found",
            detail=f"{entity} {identifier!r} does not exist",
        )


class ConflictError(HangarError):
    def __init__(self, *, detail: str) -> None:
        super().__init__(title="Conflict", status=409, type_="/errors/conflict", detail=detail)


class UnauthorizedError(HangarError):
    def __init__(self, *, detail: str | None = None) -> None:
        super().__init__(
            title="Unauthorized",
            status=401,
            type_="/errors/unauthorized",
            detail=detail or "authentication required",
        )


class ForbiddenError(HangarError):
    def __init__(self, *, detail: str) -> None:
        super().__init__(
            title="Forbidden", status=403, type_="/errors/forbidden", detail=detail
        )


class ValidationError(HangarError):
    def __init__(self, *, detail: str) -> None:
        super().__init__(
            title="Validation Failed",
            status=400,
            type_="/errors/validation",
            detail=detail,
        )


class RateLimitedError(HangarError):
    def __init__(self, *, detail: str, retry_after_s: int) -> None:
        super().__init__(
            title="Too Many Requests",
            status=429,
            type_="/errors/rate-limited",
            detail=detail,
            extras={"retry_after_s": retry_after_s},
        )
