"""Resume file storage abstraction (Phase 4.4).

Provides a provider-agnostic ``StorageProvider`` interface plus a local
filesystem implementation for the current MVP. The interface is designed so a
future S3/cloud implementation can be swapped in without changing callers.

Only the file's path (``file_uri``) and metadata are persisted in the database;
the raw bytes live on disk under a configurable root directory.
"""

from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from app.core.config import settings
from app.core.crypto import (
    StorageEncryptionError,
    decrypt_storage_bytes,
    encrypt_storage_bytes,
    is_encrypted_file,
)
from app.services.errors import NotFoundError, StoragePathTraversalError


class StorageProvider(ABC):
    """Abstract file storage service for uploaded resume files."""

    @abstractmethod
    def save(
        self,
        *,
        organization_id: uuid.UUID,
        resume_id: uuid.UUID,
        extension: str,
        stream: Callable[[], bytes],
    ) -> str:
        """Persist a file and return its opaque storage key. Raise on write failure."""

    @abstractmethod
    def save_batch_file(
        self,
        *,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
        item_id: uuid.UUID,
        extension: str,
        stream: Callable[[], bytes],
    ) -> str:
        """Persist a temporary batch file and return its opaque storage key."""

    @abstractmethod
    def save_job_file(
        self,
        *,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
        extension: str,
        stream: Callable[[], bytes],
    ) -> str:
        """Persist a job description file and return its opaque storage key."""

    @abstractmethod
    def delete(self, *, file_uri: str) -> None:
        """Delete the file at ``file_uri``. Missing files are a no-op."""

    @abstractmethod
    def read(
        self,
        *,
        file_uri: str,
        organization_id: uuid.UUID | None = None,
        file_id: uuid.UUID | None = None,
    ) -> bytes:
        """Return the raw bytes of a previously persisted file."""


class LocalFileSystemStorage(StorageProvider):
    """Store resume files on the local filesystem with containment checks.

    Files are stored under ``{root_dir}/resumes/{organization_id}/{resume_id}.{ext}``.
    The returned storage reference is an opaque relative key, preventing server
    filesystem path leakage and directory traversal.
    """

    def __init__(
        self,
        root_dir: str | Path,
        *,
        encryption_enabled: bool | None = None,
        encryption_key_id: str | None = None,
        encryption_keys: dict[str, str] | None = None,
    ) -> None:
        self._root_dir = Path(root_dir).resolve()
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._encryption_enabled = (
            settings.resume_encryption_enabled if encryption_enabled is None else encryption_enabled
        )
        self._encryption_key_id = (
            settings.resume_encryption_key_id if encryption_key_id is None else encryption_key_id
        )
        self._encryption_keys = (
            settings.resume_encryption_keys if encryption_keys is None else encryption_keys
        )
        if self._encryption_enabled and (
            not self._encryption_key_id or self._encryption_key_id not in self._encryption_keys
        ):
            raise StorageEncryptionError(
                "Storage encryption is enabled but no active key is loaded."
            )

    def _encode_file(self, payload: bytes, organization_id: uuid.UUID, file_id: uuid.UUID) -> bytes:
        if not self._encryption_enabled:
            return payload
        return encrypt_storage_bytes(
            payload,
            organization_id=organization_id,
            file_id=file_id,
            key_id=self._encryption_key_id,
            encoded_keys=self._encryption_keys,
        )

    def _resolve_path(self, file_uri: str) -> Path:
        """Resolve and validate that a storage key remains inside the storage root.

        Rejects null bytes, path traversal sequences (e.g. `../`), absolute paths
        outside storage root, and symlinks pointing outside the storage root.
        """
        if not file_uri or not isinstance(file_uri, str):
            raise StoragePathTraversalError("Invalid storage URI.")
        if "\0" in file_uri:
            raise StoragePathTraversalError("Invalid characters in storage URI.")

        raw = file_uri.strip()
        if raw.startswith("local://"):
            raw = raw[len("local://") :].lstrip("/\\")

        p = Path(raw)
        if p.is_absolute():
            resolved = p.resolve()
        else:
            resolved = (self._root_dir / p).resolve()

        try:
            resolved.relative_to(self._root_dir)
        except ValueError:
            raise StoragePathTraversalError("Access denied: path escapes storage root.") from None

        if resolved == self._root_dir:
            raise StoragePathTraversalError("Access denied: path cannot be storage root.")

        return resolved

    def save(
        self,
        *,
        organization_id: uuid.UUID,
        resume_id: uuid.UUID,
        extension: str,
        stream: Callable[[], bytes],
    ) -> str:
        clean_ext = re.sub(r"[^a-zA-Z0-9]", "", extension).lower()
        if not clean_ext:
            clean_ext = "pdf"

        relative_key = f"resumes/{organization_id}/{resume_id}.{clean_ext}"
        target_path = (self._root_dir / relative_key).resolve()

        try:
            target_path.relative_to(self._root_dir)
        except ValueError:
            raise StoragePathTraversalError(
                "Access denied: target path escapes storage root."
            ) from None

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(
            self._encode_file(stream(), organization_id=organization_id, file_id=resume_id)
        )
        return relative_key

    def save_batch_file(
        self,
        *,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
        item_id: uuid.UUID,
        extension: str,
        stream: Callable[[], bytes],
    ) -> str:
        clean_ext = re.sub(r"[^a-zA-Z0-9]", "", extension).lower()
        if not clean_ext:
            clean_ext = "pdf"

        relative_key = f"batches/{organization_id}/{batch_id}/{item_id}.{clean_ext}"
        target_path = (self._root_dir / relative_key).resolve()

        try:
            target_path.relative_to(self._root_dir)
        except ValueError:
            raise StoragePathTraversalError(
                "Access denied: target path escapes storage root."
            ) from None

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(
            self._encode_file(stream(), organization_id=organization_id, file_id=item_id)
        )
        return relative_key

    def save_job_file(
        self,
        *,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
        extension: str,
        stream: Callable[[], bytes],
    ) -> str:
        clean_ext = re.sub(r"[^a-zA-Z0-9]", "", extension).lower() or "bin"
        relative_key = f"job-descriptions/{organization_id}/{job_id}.{clean_ext}"
        target_path = (self._root_dir / relative_key).resolve()
        try:
            target_path.relative_to(self._root_dir)
        except ValueError:
            raise StoragePathTraversalError(
                "Access denied: target path escapes storage root."
            ) from None
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(
            self._encode_file(stream(), organization_id=organization_id, file_id=job_id)
        )
        return relative_key

    def cleanup_orphaned_batches(
        self,
        *,
        max_age_seconds: int = 3600,
        active_batch_ids: set[uuid.UUID] | None = None,
    ) -> int:
        """Remove batch directories older than max_age_seconds not in active_batch_ids.

        Strictly confined to {root_dir}/batches; never modifies resumes/ or other paths.
        """
        import time

        batches_dir = (self._root_dir / "batches").resolve()
        if not batches_dir.exists() or not batches_dir.is_dir():
            return 0

        now = time.time()
        active_ids = {str(bid) for bid in (active_batch_ids or set())}
        deleted_count = 0

        for org_dir in list(batches_dir.iterdir()):
            if not org_dir.is_dir():
                continue
            for batch_dir in list(org_dir.iterdir()):
                if not batch_dir.is_dir():
                    continue
                if batch_dir.name in active_ids:
                    continue

                mtime = batch_dir.stat().st_mtime
                if now - mtime >= max_age_seconds:
                    for f in list(batch_dir.iterdir()):
                        if f.is_file():
                            try:
                                f.unlink()
                                deleted_count += 1
                            except OSError:
                                pass
                    try:
                        batch_dir.rmdir()
                    except OSError:
                        pass
            try:
                org_dir.rmdir()
            except OSError:
                pass

        return deleted_count

    def delete(self, *, file_uri: str) -> None:
        target_path = self._resolve_path(file_uri)
        try:
            target_path.unlink()
        except FileNotFoundError:
            return

        # Prune empty parent directories up to storage root
        parent = target_path.parent
        while parent != self._root_dir and parent.is_relative_to(self._root_dir):
            try:
                parent.rmdir()
                parent = parent.parent
            except OSError:
                break

    def read(
        self,
        *,
        file_uri: str,
        organization_id: uuid.UUID | None = None,
        file_id: uuid.UUID | None = None,
    ) -> bytes:
        """Return the raw bytes of a previously persisted file inside storage root."""
        target_path = self._resolve_path(file_uri)
        if not target_path.exists() or not target_path.is_file():
            raise NotFoundError("Storage file not found.")
        payload = target_path.read_bytes()
        if is_encrypted_file(payload):
            if organization_id is None or file_id is None:
                raise StorageEncryptionError(
                    "Encrypted storage reads require file ownership context."
                )
            plaintext, _ = decrypt_storage_bytes(
                payload,
                organization_id=organization_id,
                file_id=file_id,
                encoded_keys=self._encryption_keys,
            )
            return plaintext
        if self._encryption_enabled:
            raise StorageEncryptionError(
                "Plaintext storage files are blocked while encryption is enabled."
            )
        return payload
