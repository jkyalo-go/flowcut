"""Thin wrapper over services.token_crypto for column-level secret sealing.

Use these to encrypt third-party API keys / provider credentials at rest.
"""

from __future__ import annotations

from services.token_crypto import decrypt_token, encrypt_token


def seal(plaintext: str | None) -> bytes | None:
    if plaintext is None or plaintext == "":
        return None
    return encrypt_token(plaintext)


def unseal(ciphertext: bytes | None) -> str | None:
    if ciphertext is None:
        return None
    return decrypt_token(bytes(ciphertext))
