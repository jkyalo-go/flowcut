import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


def get_token_key() -> bytes:
    key_hex = os.getenv("TOKEN_ENCRYPTION_KEY")
    if not key_hex:
        logger.warning(
            "TOKEN_ENCRYPTION_KEY is not set. Using insecure zero key. "
            "Set TOKEN_ENCRYPTION_KEY to a 64-character hex string in production."
        )
        key_hex = "0" * 64
    key = bytes.fromhex(key_hex)
    if len(key) != 32:
        raise ValueError(
            f"TOKEN_ENCRYPTION_KEY must be 64 hex characters (32 bytes). Got {len(key)} bytes."
        )
    return key


def encrypt_token(plaintext: str, key: bytes | None = None) -> bytes:
    if key is None:
        key = get_token_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext


def decrypt_token(ciphertext: bytes, key: bytes | None = None) -> str:
    if key is None:
        key = get_token_key()
    aesgcm = AESGCM(key)
    nonce = ciphertext[:12]
    data = ciphertext[12:]
    return aesgcm.decrypt(nonce, data, None).decode()
