"""Tests for storage service security containment (Prompt 1)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
import uuid

import pytest

from app.api.v1.routes.resumes import sanitize_download_filename
from app.services.errors import NotFoundError, StoragePathTraversalError
from app.services.storage_service import LocalFileSystemStorage, StorageProvider


def test_storage_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        StorageProvider()  # type: ignore[abstract]


def test_save_and_delete(tmp_path: Path) -> None:
    storage = LocalFileSystemStorage(tmp_path)
    org_id = uuid.uuid4()
    resume_id = uuid.uuid4()

    key = storage.save(
        organization_id=org_id,
        resume_id=resume_id,
        extension="pdf",
        stream=lambda: b"pdf-bytes",
    )

    expected = f"resumes/{org_id}/{resume_id}.pdf"
    assert key == expected
    assert not Path(key).is_absolute()
    assert (storage._root_dir / key).exists()

    content = storage.read(file_uri=key)
    assert content == b"pdf-bytes"

    storage.delete(file_uri=key)
    assert not (storage._root_dir / key).exists()


def test_delete_missing_is_noop(tmp_path: Path) -> None:
    storage = LocalFileSystemStorage(tmp_path)
    storage.delete(file_uri="resumes/nope.pdf")  # should not raise


def test_read_missing_raises_not_found(tmp_path: Path) -> None:
    storage = LocalFileSystemStorage(tmp_path)
    with pytest.raises(NotFoundError):
        storage.read(file_uri="resumes/nonexistent.pdf")


def test_read_rejects_etc_passwd(tmp_path: Path) -> None:
    storage = LocalFileSystemStorage(tmp_path)
    with pytest.raises(StoragePathTraversalError):
        storage.read(file_uri="/etc/passwd")


def test_read_rejects_directory_traversal(tmp_path: Path) -> None:
    storage = LocalFileSystemStorage(tmp_path)
    with pytest.raises(StoragePathTraversalError):
        storage.read(file_uri="../../secret.txt")

    with pytest.raises(StoragePathTraversalError):
        storage.read(file_uri="resumes/../../../secret.txt")

    with pytest.raises(StoragePathTraversalError):
        storage.read(file_uri="local://../../secret.txt")


def test_read_rejects_absolute_path_outside_root(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "confidential.pdf"
    outside_file.write_bytes(b"confidential-data")

    storage = LocalFileSystemStorage(storage_root)
    with pytest.raises(StoragePathTraversalError):
        storage.read(file_uri=str(outside_file))


def test_read_rejects_symlink_pointing_outside_root(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    outside_file = tmp_path / "target.pdf"
    outside_file.write_bytes(b"target-bytes")

    storage = LocalFileSystemStorage(storage_root)
    symlink_file = storage_root / "resumes" / "escape_link.pdf"
    symlink_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        os.symlink(outside_file, symlink_file)
        with pytest.raises(StoragePathTraversalError):
            storage.read(file_uri="resumes/escape_link.pdf")
    except OSError:
        # On Windows without SeCreateSymbolicLinkPrivilege, verify via mock resolution
        with patch.object(Path, "resolve", return_value=outside_file.resolve()):
            with pytest.raises(StoragePathTraversalError):
                storage.read(file_uri="resumes/escape_link.pdf")


def test_delete_rejects_symlink_pointing_outside_root(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    outside_file = tmp_path / "do_not_delete.pdf"
    outside_file.write_bytes(b"important-bytes")

    storage = LocalFileSystemStorage(storage_root)
    symlink_file = storage_root / "resumes" / "delete_link.pdf"
    symlink_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        os.symlink(outside_file, symlink_file)
        with pytest.raises(StoragePathTraversalError):
            storage.delete(file_uri="resumes/delete_link.pdf")
        assert outside_file.exists()
    except OSError:
        with patch.object(Path, "resolve", return_value=outside_file.resolve()):
            with pytest.raises(StoragePathTraversalError):
                storage.delete(file_uri="resumes/delete_link.pdf")
        assert outside_file.exists()


def test_delete_rejects_traversal(tmp_path: Path) -> None:
    storage = LocalFileSystemStorage(tmp_path)
    with pytest.raises(StoragePathTraversalError):
        storage.delete(file_uri="../../important.txt")


def test_read_rejects_null_bytes(tmp_path: Path) -> None:
    storage = LocalFileSystemStorage(tmp_path)
    with pytest.raises(StoragePathTraversalError):
        storage.read(file_uri="resumes/test\0.pdf")


def test_sanitize_download_filename_crlf_injection() -> None:
    # Prevents HTTP response splitting / header injection
    malicious = "cv\r\nContent-Type: text/html\r\n\r\n<script>.pdf"
    clean = sanitize_download_filename(malicious)
    assert "\r" not in clean
    assert "\n" not in clean
    assert "Content-Type" not in clean
    assert ":" not in clean


def test_sanitize_download_filename_path_traversal() -> None:
    # Prevents path traversal in filename
    traversal = "../../etc/passwd"
    clean = sanitize_download_filename(traversal)
    assert "/" not in clean
    assert "\\" not in clean
    assert ".." not in clean
    assert clean == "passwd"


def test_sanitize_download_filename_quotes_and_semicolons() -> None:
    # Prevents breaking out of Content-Disposition quotes
    quote_inject = 'candidate"; filename="evil.exe'
    clean = sanitize_download_filename(quote_inject)
    assert '"' not in clean
    assert ";" not in clean


def test_sanitize_download_filename_default_fallback() -> None:
    assert sanitize_download_filename("") == "resume.pdf"
    assert sanitize_download_filename(None) == "resume.pdf"
    assert sanitize_download_filename("   ") == "resume.pdf"
    assert sanitize_download_filename("...") == "resume.pdf"
