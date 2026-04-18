import base64
import secrets

import pytest
from cryptography.exceptions import InvalidTag

from app.core.crypto import (
    decrypt_with_dek,
    decrypt_with_master,
    encrypt_with_dek,
    encrypt_with_master,
    generate_dek,
    unwrap_dek,
    wrap_dek,
)


@pytest.fixture
def master_key_b64() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")


def test_generate_dek_is_32_bytes() -> None:
    dek = generate_dek()
    assert isinstance(dek, bytes)
    assert len(dek) == 32


def test_wrap_unwrap_roundtrip(master_key_b64: str) -> None:
    dek = generate_dek()
    wrapped = wrap_dek(dek, master_key_b64=master_key_b64)
    assert isinstance(wrapped, str)
    assert wrapped != dek.hex()

    unwrapped = unwrap_dek(wrapped, master_key_b64=master_key_b64)
    assert unwrapped == dek


def test_unwrap_fails_with_wrong_master_key(master_key_b64: str) -> None:
    dek = generate_dek()
    wrapped = wrap_dek(dek, master_key_b64=master_key_b64)

    wrong_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    with pytest.raises(InvalidTag):  # cryptography raises InvalidTag
        unwrap_dek(wrapped, master_key_b64=wrong_key)


def test_encrypt_decrypt_with_dek_roundtrip() -> None:
    dek = generate_dek()
    plaintext = "ghp_supersecrettokenvalue123456"

    ciphertext = encrypt_with_dek(plaintext, dek=dek)
    assert isinstance(ciphertext, str)
    assert ciphertext != plaintext

    decrypted = decrypt_with_dek(ciphertext, dek=dek)
    assert decrypted == plaintext


def test_encrypt_with_dek_produces_different_ciphertexts_each_time() -> None:
    dek = generate_dek()
    plaintext = "same input"

    c1 = encrypt_with_dek(plaintext, dek=dek)
    c2 = encrypt_with_dek(plaintext, dek=dek)
    assert c1 != c2  # random nonce makes each encryption unique


def test_encrypt_with_master_and_decrypt(master_key_b64: str) -> None:
    plaintext = "some data"
    ciphertext = encrypt_with_master(plaintext, master_key_b64=master_key_b64)
    decrypted = decrypt_with_master(ciphertext, master_key_b64=master_key_b64)
    assert decrypted == plaintext


def test_decrypt_with_dek_rejects_tampered_ciphertext() -> None:
    dek = generate_dek()
    ciphertext = encrypt_with_dek("x", dek=dek)

    # Flip one bit in the base64-decoded payload — decryption must raise
    raw = base64.urlsafe_b64decode(ciphertext + "==")
    tampered = raw[:15] + bytes([raw[15] ^ 0x01]) + raw[16:]
    tampered_b64 = base64.urlsafe_b64encode(tampered).decode().rstrip("=")

    with pytest.raises(InvalidTag):
        decrypt_with_dek(tampered_b64, dek=dek)
