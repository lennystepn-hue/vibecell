from app.core.errors import (
    ConflictError,
    ForbiddenError,
    HangarError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


def test_hangar_error_base_has_fields() -> None:
    err = HangarError(title="Broken", status=418, type_="/errors/broken", detail="teapot")
    assert err.title == "Broken"
    assert err.status == 418
    assert err.type == "/errors/broken"
    assert err.detail == "teapot"


def test_hangar_error_to_problem_dict() -> None:
    err = HangarError(title="X", status=500, type_="/errors/x", detail="d")
    d = err.to_problem()
    assert d == {"type": "/errors/x", "title": "X", "status": 500, "detail": "d"}


def test_not_found_defaults() -> None:
    err = NotFoundError("project", "butlr")
    assert err.status == 404
    assert err.type == "/errors/not-found"
    assert err.detail is not None
    assert "butlr" in err.detail
    assert "project" in err.detail


def test_conflict_defaults() -> None:
    err = ConflictError(detail="slug 'x' already exists")
    assert err.status == 409
    assert err.type == "/errors/conflict"


def test_unauthorized_defaults() -> None:
    err = UnauthorizedError()
    assert err.status == 401
    assert err.type == "/errors/unauthorized"


def test_forbidden_defaults() -> None:
    err = ForbiddenError(detail="not your workspace")
    assert err.status == 403
    assert err.type == "/errors/forbidden"


def test_validation_defaults() -> None:
    err = ValidationError(detail="slug too short")
    assert err.status == 400
    assert err.type == "/errors/validation"
