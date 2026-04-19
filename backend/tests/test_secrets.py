import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_inline_encrypted_roundtrip(session: AsyncSession) -> None:
    """inline_encrypted secrets store ciphertext, list masks, resolve returns plaintext."""
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "inline-sec@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})

            # Create
            r_c = await c.post(
                "/api/v1/projects/pa/secrets",
                json={"label": "stripe-key", "kind": "inline_encrypted", "reference": "sk_test_foo"},
            )
            assert r_c.status_code == 201, r_c.text
            body = r_c.json()
            assert body["label"] == "stripe-key"
            assert body["kind"] == "inline_encrypted"
            assert body["reference"] == "******"

            # List — still masked
            r_l = await c.get("/api/v1/projects/pa/secrets")
            assert r_l.status_code == 200
            assert len(r_l.json()) == 1
            assert r_l.json()[0]["reference"] == "******"

            # Resolve — plaintext
            r_r = await c.get("/api/v1/projects/pa/secrets/stripe-key/resolve")
            assert r_r.status_code == 200
            assert r_r.json()["value"] == "sk_test_foo"

            # Delete
            r_d = await c.delete("/api/v1/projects/pa/secrets/stripe-key")
            assert r_d.status_code == 204

            r_l2 = await c.get("/api/v1/projects/pa/secrets")
            assert r_l2.json() == []
    finally:
        clear_db_override()


async def test_op_reference_stored_as_is(session: AsyncSession) -> None:
    """op:// references round-trip unchanged; resolve endpoint refuses."""
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "op-sec@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})

            ref = "op://Private/Anthropic/api-key"
            r_c = await c.post(
                "/api/v1/projects/pa/secrets",
                json={"label": "anthropic-key", "kind": "op", "reference": ref},
            )
            assert r_c.status_code == 201, r_c.text
            assert r_c.json()["reference"] == ref

            r_l = await c.get("/api/v1/projects/pa/secrets")
            assert r_l.json()[0]["reference"] == ref

            # resolve endpoint rejects non-inline kinds
            r_r = await c.get("/api/v1/projects/pa/secrets/anthropic-key/resolve")
            assert r_r.status_code == 400
    finally:
        clear_db_override()


async def test_duplicate_label_rejected(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "dup-sec@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})

            r_a = await c.post(
                "/api/v1/projects/pa/secrets",
                json={"label": "same", "kind": "op", "reference": "op://a/b/c"},
            )
            assert r_a.status_code == 201

            r_b = await c.post(
                "/api/v1/projects/pa/secrets",
                json={"label": "same", "kind": "op", "reference": "op://x/y/z"},
            )
            assert r_b.status_code == 409
    finally:
        clear_db_override()
