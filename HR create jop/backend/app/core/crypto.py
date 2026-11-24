"""Authenticated encryption for files stored by the recruitment service."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENCRYPTED_FILE_MAGIC = b"HERAENC\x01"
NONCE_BYTES = 12
TAG_BYTES = 16
MAX_KEY_ID_BYTES = 64


class StorageEncryptionError(ValueError):
    """Raised when an encrypted storage object is malformed or cannot authenticate."""


def _google_token_key() -> bytes:
    """Return the dedicated key used by the existing Google OAuth token format."""
    from app.core.config import settings

    key_material = settings.google_token_encryption_key
    if not key_material:
        raise StorageEncryptionError("The Google token encryption key is unavailable.")
    return hashlib.sha256(key_material.encode("utf-8")).digest()


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a Google OAuth token using the legacy, version-compatible format."""
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(_google_token_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_secret(encoded: str) -> str:
    """Decrypt a Google OAuth token produced by the legacy format."""
    try:
        data = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError, binascii.Error):
        raise StorageEncryptionError("The stored Google token is invalid.") from None
    if len(data) < NONCE_BYTES + TAG_BYTES:
        raise StorageEncryptionError("The stored Google token is invalid.")
    try:
        plaintext = AESGCM(_google_token_key()).decrypt(data[:NONCE_BYTES], data[NONCE_BYTES:], None)
    except InvalidTag:
        raise StorageEncryptionError("The stored Google token failed authentication.") from None
    return plaintext.decode("utf-8")


def is_encrypted_file(data: bytes) -> bool:
    return data.startswith(ENCRYPTED_FILE_MAGIC)


def _key_bytes(key_id: str, encoded_keys: dict[str, str]) -> bytes:
    encoded = encoded_keys.get(key_id)
    if encoded is None:
        raise StorageEncryptionError("The storage encryption key is unavailable.")
    try:
        key = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise StorageEncryptionError("The storage encryption key is invalid.") from None
    if len(key) != 32:
        raise StorageEncryptionError("The storage encryption key is invalid.")
    return key


def _associated_data(organization_id: uuid.UUID, file_id: uuid.UUID, key_id: str) -> bytes:
    try:
        key_id_bytes = key_id.encode("ascii")
    except UnicodeEncodeError:
        raise StorageEncryptionError("The storage encryption key id is invalid.") from None
    if not 1 <= len(key_id_bytes) <= MAX_KEY_ID_BYTES:
        raise StorageEncryptionError("The storage encryption key id is invalid.")
    return b"hera-storage-v1\0" + organization_id.bytes + file_id.bytes + key_id_bytes


def encrypt_storage_bytes(
    plaintext: bytes,
    *,
    organization_id: uuid.UUID,
    file_id: uuid.UUID,
    key_id: str,
    encoded_keys: dict[str, str],
) -> bytes:
    key_id_bytes = key_id.encode("ascii")
    associated_data = _associated_data(organization_id, file_id, key_id)
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(_key_bytes(key_id, encoded_keys)).encrypt(nonce, plaintext, associated_data)
    return ENCRYPTED_FILE_MAGIC + bytes([len(key_id_bytes)]) + key_id_bytes + nonce + ciphertext


def decrypt_storage_bytes(
    envelope: bytes,
    *,
    organization_id: uuid.UUID,
    file_id: uuid.UUID,
    encoded_keys: dict[str, str],
) -> tuple[bytes, str]:
    minimum_size = len(ENCRYPTED_FILE_MAGIC) + 1 + 1 + NONCE_BYTES + TAG_BYTES
    if not is_encrypted_file(envelope) or len(envelope) < minimum_size:
        raise StorageEncryptionError("The stored file is not a valid encrypted object.")

    key_id_length = envelope[len(ENCRYPTED_FILE_MAGIC)]
    if not 1 <= key_id_length <= MAX_KEY_ID_BYTES:
        raise StorageEncryptionError("The stored file encryption header is invalid.")
    key_start = len(ENCRYPTED_FILE_MAGIC) + 1
    key_end = key_start + key_id_length
    nonce_end = key_end + NONCE_BYTES
    if len(envelope) < nonce_end + TAG_BYTES:
        raise StorageEncryptionError("The stored file encryption header is invalid.")
    try:
        key_id = envelope[key_start:key_end].decode("ascii")
    except UnicodeDecodeError:
        raise StorageEncryptionError("The stored file encryption header is invalid.") from None
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", key_id):
        raise StorageEncryptionError("The stored file encryption header is invalid.")

    nonce = envelope[key_end:nonce_end]
    try:
        plaintext = AESGCM(_key_bytes(key_id, encoded_keys)).decrypt(
            nonce,
            envelope[nonce_end:],
            _associated_data(organization_id, file_id, key_id),
        )
    except InvalidTag:
        raise StorageEncryptionError("The stored file failed authentication.") from None
    return plaintext, key_id
