from pydantic import BaseModel, ConfigDict, Field, field_validator

_ALLOWED_KINDS = {"inline_encrypted", "op", "bw", "ssh_agent", "env_path", "keychain"}


class SecretOut(BaseModel):
    """Public shape of a secret reference.

    For `inline_encrypted`, the service masks `reference` to "******" before
    returning — callers never see ciphertext via normal list/get. For the
    other kinds, `reference` is a path-style string (e.g. `op://Vault/Item/field`)
    which is not itself sensitive and is returned as-is.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    kind: str
    reference: str


class SecretIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    kind: str = Field(..., min_length=1, max_length=30)
    reference: str = Field(..., min_length=1, max_length=2000)

    @field_validator("kind")
    @classmethod
    def _validate_kind(cls, v: str) -> str:
        if v not in _ALLOWED_KINDS:
            raise ValueError(f"kind must be one of {sorted(_ALLOWED_KINDS)}")
        return v


class SecretValueOut(BaseModel):
    value: str
