from __future__ import annotations

import base64
import hashlib
import uuid
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.crypto import StorageEncryptionError, decrypt_storage_bytes, encrypt_storage_bytes
from app.services.storage_service import LocalFileSystemStorage
from tools.migrate_storage_encryption import migrate_storage


def _keyring() -> tuple[str, dict[str, str]]:
    key_id = "test-key-1"
    return key_id, {key_id: base64.b64encode(b"k" * 32).decode("ascii")}


def test_settings_require_encryption_in_production_and_require_key_when_enabled() -> None:
    with pytest.raises(ValueError, match="RESUME_ENCRYPTION_ENABLED"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="secure-test-jwt-secret-key-0123456789",
            resume_encryption_enabled=False,
        )
    with pytest.raises(ValueError, match="RESUME_ENCRYPTION_KEYS"):
        Settings(
            _env_file=None,
            app_env="test",
            jwt_secret_key="secure-test-jwt-secret-key-0123456789",
            resume_encryption_enabled=True,
            resume_encryption_key_id="missing-key",
            resume_encryption_keys={},
        )
    key_id, keys = _keyring()
    production_settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret_key="secure-test-jwt-secret-key-0123456789",
        resume_encryption_enabled=True,
        resume_encryption_key_id=key_id,
        resume_encryption_keys=keys,
    )
    assert production_settings.resume_encryption_enabled is True


def test_aes_gcm_binds_ciphertext_to_org_and_file_ids() -> None:
    key_id, keys = _keyring()
    org_id, file_id = uuid.uuid4(), uuid.uuid4()
    encrypted = encrypt_storage_bytes(
        b"sensitive resume bytes",
        organization_id=org_id,
        file_id=file_id,
        key_id=key_id,
        encoded_keys=keys,
    )

    plaintext, used_key_id = decrypt_storage_bytes(
        encrypted, organization_id=org_id, file_id=file_id, encoded_keys=keys
    )
    assert plaintext == b"sensitive resume bytes"
    assert used_key_id == key_id
    with pytest.raises(StorageEncryptionError):
        decrypt_storage_bytes(
            encrypted, organization_id=uuid.uuid4(), file_id=file_id, encoded_keys=keys
        )
    with pytest.raises(StorageEncryptionError):
        decrypt_storage_bytes(
            encrypted, organization_id=org_id, file_id=uuid.uuid4(), encoded_keys=keys
        )
    tampered = encrypted[:-1] + bytes([encrypted[-1] ^ 1])
    with pytest.raises(StorageEncryptionError):
        decrypt_storage_bytes(tampered, organization_id=org_id, file_id=file_id, encoded_keys=keys)


def test_storage_encrypts_on_write_and_requires_context_to_read(tmp_path: Path) -> None:
    key_id, keys = _keyring()
    org_id, resume_id = uuid.uuid4(), uuid.uuid4()
    storage = LocalFileSystemStorage(
        tmp_path,
        encryption_enabled=True,
        encryption_key_id=key_id,
        encryption_keys=keys,
    )
    file_uri = storage.save(
        organization_id=org_id,
        resume_id=resume_id,
        extension="pdf",
        stream=lambda: b"private resume text",
    )
    ciphertext = (tmp_path / file_uri).read_bytes()
    assert b"private resume text" not in ciphertext
    with pytest.raises(StorageEncryptionError):
        storage.read(file_uri=file_uri)
    assert (
        storage.read(file_uri=file_uri, organization_id=org_id, file_id=resume_id)
        == b"private resume text"
    )


def test_encrypted_mode_rejects_plaintext_and_missing_active_key(tmp_path: Path) -> None:
    key_id, keys = _keyring()
    plaintext_uri = "resumes/plain.pdf"
    path = tmp_path / plaintext_uri
    path.parent.mkdir(parents=True)
    path.write_bytes(b"plaintext")
    storage = LocalFileSystemStorage(
        tmp_path,
        encryption_enabled=True,
        encryption_key_id=key_id,
        encryption_keys=keys,
    )
    with pytest.raises(StorageEncryptionError):
        storage.read(file_uri=plaintext_uri, organization_id=uuid.uuid4(), file_id=uuid.uuid4())
    with pytest.raises(StorageEncryptionError):
        LocalFileSystemStorage(
            tmp_path, encryption_enabled=True, encryption_key_id="missing", encryption_keys=keys
        )


def test_storage_migration_backs_up_verifies_and_replaces_only_afterward(tmp_path: Path) -> None:
    key_id, keys = _keyring()
    org_id, resume_id = uuid.uuid4(), uuid.uuid4()
    storage_root = tmp_path / "storage"
    source = storage_root / "resumes" / str(org_id) / f"{resume_id}.pdf"
    source.parent.mkdir(parents=True)
    plaintext = b"migration test bytes"
    source.write_bytes(plaintext)
    backup_root = tmp_path / "external-backup"

    preview = migrate_storage(
        storage_root=storage_root,
        backup_root=None,
        dry_run=True,
        active_key_id=key_id,
        encoded_keys=keys,
    )
    assert preview["to_encrypt"] == 1
    assert source.read_bytes() == plaintext
    assert not backup_root.exists()

    applied = migrate_storage(
        storage_root=storage_root,
        backup_root=backup_root,
        dry_run=False,
        active_key_id=key_id,
        encoded_keys=keys,
    )
    assert applied["to_encrypt"] == 1
    resumed = migrate_storage(
        storage_root=storage_root,
        backup_root=backup_root,
        dry_run=False,
        active_key_id=key_id,
        encoded_keys=keys,
    )
    assert resumed["to_encrypt"] == 0
    ciphertext = source.read_bytes()
    assert plaintext not in ciphertext
    assert (
        hashlib.sha256((backup_root / source.relative_to(storage_root)).read_bytes()).digest()
        == hashlib.sha256(plaintext).digest()
    )
    recovered, _ = decrypt_storage_bytes(
        ciphertext, organization_id=org_id, file_id=resume_id, encoded_keys=keys
    )
    assert recovered == plaintext
    assert not list(storage_root.rglob("*.encrypting"))
