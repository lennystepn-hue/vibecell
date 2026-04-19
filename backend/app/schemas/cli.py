"""Schemas for the CLI device-code pairing flow (Spec 3 §4.2)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PairStartResponse(BaseModel):
    device_code: str
    user_code: str
    verification_url: str
    expires_in: int  # seconds


class PairCompleteRequest(BaseModel):
    device_code: str = Field(..., min_length=10)


class PairCompleteResponse(BaseModel):
    token: str  # raw bearer token — caller must store it; server only keeps sha256
    device_id: str
    user_id: str
    workspace_id: str
    workspace_slug: str


class PairConfirmRequest(BaseModel):
    user_code: str = Field(..., pattern=r"^[A-Z0-9]{4}-[A-Z0-9]{4}$")
    device_name: str | None = Field(default=None, max_length=100)


class DeviceOut(BaseModel):
    id: str
    name: str | None
    paired_at: str  # ISO-8601
    last_seen_at: str | None


class PairPendingStatus(BaseModel):
    status: str = "pending"
