from httpx import ASGITransport, AsyncClient

from app.core.errors import NotFoundError, RateLimitedError


async def test_hangar_error_becomes_problem_json() -> None:
    from fastapi import FastAPI

    from app.core.problem import install_problem_handler

    test_app = FastAPI()
    install_problem_handler(test_app)

    @test_app.get("/boom")
    async def boom() -> None:
        raise NotFoundError("project", "butlr")

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://t") as c:
        resp = await c.get("/boom")
    assert resp.status_code == 404
    body = resp.json()
    assert body["type"] == "/errors/not-found"
    assert body["title"] == "Not Found"
    assert body["status"] == 404
    assert "butlr" in body["detail"]


async def test_rate_limited_adds_retry_after_header() -> None:
    from fastapi import FastAPI

    from app.core.problem import install_problem_handler

    test_app = FastAPI()
    install_problem_handler(test_app)

    @test_app.get("/boom")
    async def boom() -> None:
        raise RateLimitedError(detail="slow down", retry_after_s=42)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://t") as c:
        resp = await c.get("/boom")
    assert resp.status_code == 429
    assert resp.headers.get("retry-after") == "42"
    body = resp.json()
    assert body["retry_after_s"] == 42
