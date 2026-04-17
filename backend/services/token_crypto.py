import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def get_token_key() -> bytes:
    key_hex = os.getenv("TOKEN_ENCRYPTION_KEY", "0" * 64)
    return bytes.fromhex(key_hex)


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
