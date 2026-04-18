"""AES-256-GCM envelope crypto for Hangar.

Layer 1: HANGAR_MASTER_KEY (32 bytes, env) wraps per-workspace DEKs.
Layer 2: DEK (32 bytes, per workspace) encrypts integration tokens and
         other workspace-scoped secrets at rest.

Every ciphertext payload is base64-urlsafe-encoded:

    +----------+--------------+------------+
    | nonce 12 | ciphertext n | tag 16     |
    +----------+--------------+------------+

Note on AAD (associated data): v1 does not bind ciphertext to
(workspace_id, entity, entity_id) via AAD. This is acceptable because
DEKs are per-workspace, so cross-workspace swap is already prevented by
key isolation. However, *intra-workspace* swap (e.g., copying
integrations.token_ciphertext from row A to row B in the same workspace)
is undetectable. AAD binding is a forward-compatible add — flip it on
after re-encrypting all stored payloads in a Phase 4+ migration.

`cryptography.hazmat.primitives.ciphers.aead.AESGCM` embeds the auth tag
into the ciphertext, so our encoded layout is nonce + AESGCM.encrypt_output.
"""
from __future__ import annotations

import base64
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _master_key_bytes(master_key_b64: str) -> bytes:
    raw = _b64decode(master_key_b64)
    if len(raw) != 32:
        raise ValueError(f"HANGAR_MASTER_KEY must decode to 32 bytes (got {len(raw)})")
    return raw


def generate_dek() -> bytes:
    """Return a fresh 32-byte data encryption key."""
    return secrets.token_bytes(32)


def _encrypt(plaintext: bytes, key: bytes) -> str:
    aes = AESGCM(key)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ciphertext = aes.encrypt(nonce, plaintext, associated_data=None)
    return _b64encode(nonce + ciphertext)


def _decrypt(payload_b64: str, key: bytes) -> bytes:
    raw = _b64decode(payload_b64)
    if len(raw) < _NONCE_BYTES + 16:
        raise ValueError("ciphertext too short")
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    aes = AESGCM(key)
    return aes.decrypt(nonce, ciphertext, associated_data=None)


def wrap_dek(dek: bytes, *, master_key_b64: str) -> str:
    """Encrypt a DEK with the server master key, return base64 string."""
    return _encrypt(dek, _master_key_bytes(master_key_b64))


def unwrap_dek(wrapped_b64: str, *, master_key_b64: str) -> bytes:
    """Decrypt a wrapped DEK, return 32 bytes."""
    return _decrypt(wrapped_b64, _master_key_bytes(master_key_b64))


def encrypt_with_dek(plaintext: str, *, dek: bytes) -> str:
    """Encrypt a UTF-8 string with a workspace DEK, return base64 payload."""
    return _encrypt(plaintext.encode("utf-8"), dek)


def decrypt_with_dek(payload_b64: str, *, dek: bytes) -> str:
    """Decrypt a workspace-DEK-encrypted payload, return UTF-8 string."""
    return _decrypt(payload_b64, dek).decode("utf-8")


def encrypt_with_master(plaintext: str, *, master_key_b64: str) -> str:
    """Convenience: encrypt directly with the master key (one-layer, small payloads)."""
    return _encrypt(plaintext.encode("utf-8"), _master_key_bytes(master_key_b64))


def decrypt_with_master(payload_b64: str, *, master_key_b64: str) -> str:
    """Convenience: decrypt master-encrypted payload."""
    return _decrypt(payload_b64, _master_key_bytes(master_key_b64)).decode("utf-8")
