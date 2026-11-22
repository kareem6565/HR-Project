"""Back up and migrate local storage files to authenticated encryption.

Dry-run is the default. Apply runs require an explicit backup directory outside
the repository and storage root. Plaintext is kept in memory only during conversion.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.crypto import (
    decrypt_storage_bytes,
    encrypt_storage_bytes,
    is_encrypted_file,
)


@dataclass(frozen=True)
class FileContext:
    organization_id: uuid.UUID
    file_id: uuid.UUID


def _file_context(relative_path: Path) -> FileContext:
    parts = relative_path.parts
    try:
        if len(parts) == 3 and parts[0] == "resumes":
            return FileContext(uuid.UUID(parts[1]), uuid.UUID(Path(parts[2]).stem))
        if len(parts) == 4 and parts[0] == "batches":
            return FileContext(uuid.UUID(parts[1]), uuid.UUID(Path(parts[3]).stem))
        if len(parts) == 3 and parts[0] == "job-descriptions":
            return FileContext(uuid.UUID(parts[1]), uuid.UUID(Path(parts[2]).stem))
    except ValueError as error:
        raise ValueError(
            "Storage contains a file with an unsupported or invalid storage key."
        ) from error
    raise ValueError("Storage contains a file with an unsupported or invalid storage key.")


def _read_plaintext(
    source: Path,
    context: FileContext,
    encoded_keys: dict[str, str],
) -> tuple[bytes, str | None]:
    content = source.read_bytes()
    if not is_encrypted_file(content):
        return content, None
    return decrypt_storage_bytes(
        content,
        organization_id=context.organization_id,
        file_id=context.file_id,
        encoded_keys=encoded_keys,
    )


def _backup_all(
    files: list[Path],
    root: Path,
    backup_root: Path,
    contexts: dict[Path, FileContext],
    encoded_keys: dict[str, str],
) -> int:
    backup_root.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for source in files:
        relative = source.relative_to(root)
        destination = backup_root / relative
        if destination.is_symlink() or backup_root not in destination.resolve().parents:
            raise OSError("Storage backup contains an unsafe path.")
        if not destination.exists():
            if is_encrypted_file(source.read_bytes()):
                raise OSError(
                    "An encrypted source has no verified original backup; migration stopped."
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        source_plain, _ = _read_plaintext(source, contexts[source], encoded_keys)
        backup_plain, _ = _read_plaintext(destination, contexts[source], encoded_keys)
        if hashlib.sha256(source_plain).digest() != hashlib.sha256(backup_plain).digest():
            raise OSError("Storage backup verification failed.")
        total_bytes += destination.stat().st_size
    return total_bytes


def migrate_storage(
    *,
    storage_root: Path,
    backup_root: Path | None,
    dry_run: bool,
    active_key_id: str,
    encoded_keys: dict[str, str],
) -> dict[str, int]:
    root = storage_root.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("Storage root does not exist or is not a directory.")
    if active_key_id not in encoded_keys:
        raise ValueError("The active encryption key is not available.")
    repository_root = Path(__file__).resolve().parents[3]

    files = sorted(path for path in root.rglob("*") if path.is_file())
    if any(path.is_symlink() or root not in path.resolve().parents for path in files):
        raise ValueError("Storage contains a symlink or a file outside the storage root.")
    contexts = {path: _file_context(path.relative_to(root)) for path in files}
    key_ids: dict[Path, str | None] = {}
    for source in files:
        plaintext, current_key_id = _read_plaintext(source, contexts[source], encoded_keys)
        del plaintext
        key_ids[source] = current_key_id

    to_encrypt = [path for path in files if key_ids[path] != active_key_id]
    if not dry_run:
        if backup_root is None:
            raise ValueError("--backup-dir is required with --apply.")
        backup = backup_root.resolve()
        if (
            backup == root
            or root in backup.parents
            or backup == repository_root
            or repository_root in backup.parents
        ):
            raise ValueError(
                "The backup directory must be outside the repository and storage root."
            )
        _backup_all(files, root, backup, contexts, encoded_keys)

        for source in to_encrypt:
            context = contexts[source]
            plaintext, _ = _read_plaintext(source, context, encoded_keys)
            expected_digest = hashlib.sha256(plaintext).digest()
            envelope = encrypt_storage_bytes(
                plaintext,
                organization_id=context.organization_id,
                file_id=context.file_id,
                key_id=active_key_id,
                encoded_keys=encoded_keys,
            )
            temporary = source.with_name(f".{source.name}.encrypting")
            try:
                with temporary.open("xb") as encrypted_file:
                    encrypted_file.write(envelope)
                    encrypted_file.flush()
                    os.fsync(encrypted_file.fileno())
                verified, verified_key_id = _read_plaintext(temporary, context, encoded_keys)
                if (
                    verified_key_id != active_key_id
                    or hashlib.sha256(verified).digest() != expected_digest
                ):
                    raise OSError("Encrypted file verification failed.")
                os.replace(temporary, source)
            finally:
                if temporary.exists():
                    temporary.unlink()

    return {
        "files": len(files),
        "already_encrypted": sum(key_id == active_key_id for key_id in key_ids.values()),
        "to_encrypt": len(to_encrypt),
        "backup_bytes": sum(path.stat().st_size for path in files) if dry_run else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=Path(settings.storage_root_dir))
    parser.add_argument("--backup-dir", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Back up and replace files in place.")
    mode.add_argument("--dry-run", action="store_true", help="Preview without writing files.")
    args = parser.parse_args()

    try:
        summary = migrate_storage(
            storage_root=args.storage_root,
            backup_root=args.backup_dir,
            dry_run=not args.apply,
            active_key_id=settings.resume_encryption_key_id,
            encoded_keys=settings.resume_encryption_keys,
        )
    except (OSError, ValueError) as error:
        print(f"Storage migration stopped: {error}", file=sys.stderr)
        return 1

    action = "Dry run" if not args.apply else "Encrypted migration"
    print(
        f"{action}: {summary['files']} files found, "
        f"{summary['already_encrypted']} already use the active key, "
        f"{summary['to_encrypt']} require encryption."
    )
    if not args.apply:
        print("No files or backups were written. Use --backup-dir OUTSIDE_REPO --apply to migrate.")
    else:
        print("Original files were backed up, authenticated, and atomically replaced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
