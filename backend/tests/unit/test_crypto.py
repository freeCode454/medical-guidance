from app.common.crypto import (
    PREFIX,
    decrypt_secret,
    encrypt_secret,
    is_encrypted,
)


def test_roundtrip() -> None:
    plaintext = "sk-test-1234567890"
    ciphertext = encrypt_secret(plaintext)
    assert ciphertext is not None
    assert ciphertext != plaintext
    assert ciphertext.startswith(PREFIX)
    assert decrypt_secret(ciphertext) == plaintext


def test_encrypt_is_idempotent() -> None:
    once = encrypt_secret("sk-test")
    assert once is not None
    assert encrypt_secret(once) == once


def test_same_plaintext_has_different_ciphertext() -> None:
    first = encrypt_secret("sk-test")
    second = encrypt_secret("sk-test")
    assert first != second


def test_legacy_plaintext_is_readable() -> None:
    assert is_encrypted("sk-legacy") is False
    assert decrypt_secret("sk-legacy") == "sk-legacy"


def test_empty_value() -> None:
    assert encrypt_secret("") is None
    assert encrypt_secret(None) is None
    assert decrypt_secret("") is None
    assert decrypt_secret(None) is None
