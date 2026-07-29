"""One-time pairing codes and the /i/{code} one-liner carrier (issue #4).

The code is the credential that lets a script on a machine with no session
reach a device token. Three properties carry that trust, and each gets a test
that fails loudly if it ever stops holding: single-use, time-bounded, and
device-pairing-only.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services import onboarding_pair as pair_svc

# ── Code generation ───────────────────────────────────────────────────────


def test_code_avoids_ambiguous_characters() -> None:
    # A code gets read off a screen and typed. 0/O and 1/I/L must not appear
    # or a correctly-copied code will still fail for some users.
    forbidden = set("01OILU")
    for _ in range(200):
        assert not (set(pair_svc.gen_code()) & forbidden)


def test_code_is_long_enough_to_be_unguessable() -> None:
    # 30^8 ≈ 6.6e11 within a 10-minute single-use window.
    assert len(pair_svc.gen_code()) == 8


def test_ttl_is_sized_for_a_human_opening_a_terminal() -> None:
    # Regression guard on a deliberate decision: 60s was considered and
    # rejected because it expires mid-paste.
    assert pair_svc._TTL_SECONDS == 600


# ── Endpoint shape ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mint_requires_auth(client: AsyncClient) -> None:
    r = await client.post("/api/v1/onboarding/code")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_mint_returns_both_one_liners(authed_client: AsyncClient) -> None:
    r = await authed_client.post("/api/v1/onboarding/code")
    assert r.status_code == 200
    body = r.json()
    assert len(body["code"]) == 8
    assert body["expires_in"] == 600
    assert body["code"] in body["install_sh"]
    assert body["code"] in body["install_ps1"]
    assert body["install_sh"].startswith("curl ")
    assert body["install_ps1"].startswith("irm ")


@pytest.mark.asyncio
async def test_two_mints_never_collide(authed_client: AsyncClient) -> None:
    first = (await authed_client.post("/api/v1/onboarding/code")).json()["code"]
    second = (await authed_client.post("/api/v1/onboarding/code")).json()["code"]
    assert first != second


# ── Redemption ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redeem_yields_a_device_token(authed_client: AsyncClient, client: AsyncClient) -> None:
    code = (await authed_client.post("/api/v1/onboarding/code")).json()["code"]

    # Anonymous on purpose: the machine running the one-liner has no session.
    r = await client.post(
        "/api/v1/onboarding/redeem",
        json={"code": code, "device_name": "test-box"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["device_id"]
    assert body["workspace_slug"]


@pytest.mark.asyncio
async def test_a_code_cannot_be_redeemed_twice(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    """The property the whole security argument rests on.

    The code sits in shell history. Single-use is what makes that survivable:
    by the time anyone reads it there, it has been spent.
    """
    code = (await authed_client.post("/api/v1/onboarding/code")).json()["code"]

    first = await client.post("/api/v1/onboarding/redeem", json={"code": code})
    assert first.status_code == 200

    second = await client.post("/api/v1/onboarding/redeem", json={"code": code})
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_unknown_code_is_rejected(client: AsyncClient) -> None:
    r = await client.post("/api/v1/onboarding/redeem", json={"code": "ZZZZZZZZ"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_redeemed_device_appears_and_is_revocable(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    """The escape hatch the security note promises must actually exist."""
    code = (await authed_client.post("/api/v1/onboarding/code")).json()["code"]
    device_id = (
        await client.post(
            "/api/v1/onboarding/redeem",
            json={"code": code, "device_name": "revoke-me"},
        )
    ).json()["device_id"]

    listed = (await authed_client.get("/api/v1/cli/devices")).json()
    assert any(d["id"] == device_id for d in listed)

    assert (await authed_client.delete(f"/api/v1/cli/devices/{device_id}")).status_code == 204
    listed_after = (await authed_client.get("/api/v1/cli/devices")).json()
    assert not any(d["id"] == device_id for d in listed_after)


@pytest.mark.asyncio
async def test_code_is_not_a_session_token(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    """Scope check: the code grants device pairing and nothing else.

    Presenting it as a bearer token must not open any authed surface.
    """
    code = (await authed_client.post("/api/v1/onboarding/code")).json()["code"]
    r = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {code}"})
    assert r.status_code == 401


# ── /i/{code} ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_install_link_bakes_the_code_into_a_shell_shim(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    code = (await authed_client.post("/api/v1/onboarding/code")).json()["code"]
    r = await client.get(f"/i/{code}")
    assert r.status_code == 200
    assert f"HANGAR_SETUP_CODE={code}" in r.text
    assert "install.sh" in r.text
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_install_link_serves_powershell_to_powershell(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    code = (await authed_client.post("/api/v1/onboarding/code")).json()["code"]
    r = await client.get(
        f"/i/{code}",
        headers={"user-agent": "Mozilla/5.0 (Windows NT; WindowsPowerShell/5.1.22621)"},
    )
    assert "$env:HANGAR_SETUP_CODE" in r.text
    assert "install.ps1" in r.text


@pytest.mark.asyncio
async def test_install_link_does_not_consume_the_code(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    """Fetching the script must leave the code spendable — the installer
    still needs it a moment later."""
    code = (await authed_client.post("/api/v1/onboarding/code")).json()["code"]
    await client.get(f"/i/{code}")
    assert (
        await client.post("/api/v1/onboarding/redeem", json={"code": code})
    ).status_code == 200


@pytest.mark.asyncio
async def test_dead_link_explains_itself_instead_of_breaking_the_pipe(
    client: AsyncClient,
) -> None:
    """A 404 body piped into `sh` is a parse error, not a message.

    Anyone hitting an expired link is already confused; the shell they pasted
    into should tell them what to do rather than emit syntax noise.
    """
    r = await client.get("/i/ZZZZZZZZ")
    assert r.status_code == 200
    assert "expired" in r.text.lower()
    assert "exit 1" in r.text
    assert "install.sh" not in r.text
