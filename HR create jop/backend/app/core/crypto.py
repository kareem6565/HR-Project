from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _derive_key(raw: str) -> bytes:
    # Deterministic 32-byte key derivation from configured secret material.
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret string for storage. Returns base64(nonce+ciphertext)."""
    key_material = settings.google_token_encryption_key
    if not key_material:
        raise ValueError("GOOGLE_TOKEN_ENCRYPTION_KEY is not configured.")
    aesgcm = AESGCM(_derive_key(key_material))
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_secret(encoded: str) -> str:
    """Decrypt a value produced by encrypt_secret."""
    key_material = settings.google_token_encryption_key
    if not key_material:
        raise ValueError("GOOGLE_TOKEN_ENCRYPTION_KEY is not configured.")
    data = base64.b64decode(encoded.encode("ascii"))
    nonce, ciphertext = data[:12], data[12:]
    aesgcm = AESGCM(_derive_key(key_material))
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
