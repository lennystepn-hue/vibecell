"""Pydantic request/response DTOs for OAuth endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# ---- Dynamic Client Registration (RFC 7591) ----

class RegisterRequest(BaseModel):
    client_name: str | None = Field(None, max_length=255)
    redirect_uris: list[str] = Field(..., min_length=1, max_length=10)
    scope: str = "vibecell:tools"

    @field_validator("redirect_uris")
    @classmethod
    def validate_redirect_uris(cls, v: list[str]) -> list[str]:
        for uri in v:
            low = uri.lower()
            if low.startswith("https://"):
                continue
            if low.startswith("http://127.0.0.1") or low.startswith("http://localhost"):
                continue
            raise ValueError(f"redirect_uri must be HTTPS or loopback: {uri}")
        return v


class RegisterResponse(BaseModel):
    client_id: str
    client_id_issued_at: int
    client_name: str | None
    redirect_uris: list[str]
    scope: str
    token_endpoint_auth_method: str = "none"


# ---- Authorization ----

class AuthorizeParams(BaseModel):
    response_type: str
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    state: str
    scope: str = "vibecell:tools"

    @field_validator("response_type")
    @classmethod
    def must_be_code(cls, v: str) -> str:
        if v != "code":
            raise ValueError("response_type must be 'code'")
        return v

    @field_validator("code_challenge_method")
    @classmethod
    def must_be_s256(cls, v: str) -> str:
        if v != "S256":
            raise ValueError("code_challenge_method must be 'S256'")
        return v


class GrantRequest(BaseModel):
    state: str
    workspace_id: str


# ---- Token ----

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str
