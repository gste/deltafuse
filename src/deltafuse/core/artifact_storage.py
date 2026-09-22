"""Single-file atomic publication primitives (AW-07).

Provides same-filesystem staging, fsync durability, readback verification,
platform-correct no-replace create, and atomic replacement update without
truncate-and-rewrite fallbacks.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import time
import uuid


class ArtifactStorageError(Exception):
    """Raised when atomic storage operations fail."""

    def __init__(self, message: str, *, code: str, path: str | None = None):
        super().__init__(f"[{code}] {message}")
        self.message = message
        self.code = code
        self.path = path


def stage_artifact_bytes(target_path: Path, content_bytes: bytes) -> tuple[Path, str]:
    """Write bytes to a staged temp file in the target's parent directory.

    Flushes, fsyncs, and verifies read-back digest before returning.
    Returns (staged_path, digest).
    """
    target_path = Path(target_path)
    parent = target_path.parent
    parent.mkdir(parents=True, exist_ok=True)

    expected_digest = hashlib.sha256(content_bytes).hexdigest()
    staging_filename = f"{target_path.name}.tmp.{uuid.uuid4().hex}"
    staged_path = parent / staging_filename

    try:
        with open(staged_path, "wb") as f:
            f.write(content_bytes)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # Fsync might not be supported on some virtual/mounted filesystems
                pass

        # Readback verification
        readback_bytes = staged_path.read_bytes()
        readback_digest = hashlib.sha256(readback_bytes).hexdigest()
        if readback_digest != expected_digest:
            if staged_path.exists():
                staged_path.unlink(missing_ok=True)
            raise ArtifactStorageError(
                "Staged content readback checksum mismatch",
                code="validation_failed",
                path=str(target_path),
            )

        return staged_path, expected_digest

    except Exception as ex:
        if staged_path.exists():
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(ex, ArtifactStorageError):
            raise
        raise ArtifactStorageError(
            f"Failed to stage artifact bytes: {ex}",
            code="atomic_write_failed",
            path=str(target_path),
        ) from ex


def atomic_create(target_path: Path, content_bytes: bytes) -> str:
    """Atomic no-replace creation of a new file.

    Guarantees target path does not exist prior to creation, and exactly one
    creator succeeds when multiple callers race concurrently.
    Returns SHA256 of published content.
    """
    target_path = Path(target_path)
    if target_path.exists():
        raise ArtifactStorageError(
            f"Target path '{target_path}' already exists",
            code="already_exists",
            path=str(target_path),
        )

    staged_path, digest = stage_artifact_bytes(target_path, content_bytes)

    try:
        if os.name == "nt":
            # On Windows, os.rename fails with FileExistsError if target exists
            try:
                os.rename(staged_path, target_path)
            except FileExistsError as ex:
                raise ArtifactStorageError(
                    f"Target path '{target_path}' already exists",
                    code="already_exists",
                    path=str(target_path),
                ) from ex
        else:
            # POSIX: os.link creates hardlink and fails with FileExistsError if target exists
            try:
                os.link(staged_path, target_path)
                os.unlink(staged_path)
            except FileExistsError as ex:
                raise ArtifactStorageError(
                    f"Target path '{target_path}' already exists",
                    code="already_exists",
                    path=str(target_path),
                ) from ex
            except OSError:
                if target_path.exists():
                    raise ArtifactStorageError(
                        f"Target path '{target_path}' already exists",
                        code="already_exists",
                        path=str(target_path),
                    )
                try:
                    fd = os.open(target_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                    os.replace(staged_path, target_path)
                except FileExistsError as ex:
                    raise ArtifactStorageError(
                        f"Target path '{target_path}' already exists",
                        code="already_exists",
                        path=str(target_path),
                    ) from ex

    except Exception:
        if staged_path.exists():
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    return digest


def atomic_replace(
    target_path: Path,
    content_bytes: bytes,
    expected_sha256: str | None = None,
) -> str:
    """Atomic replacement update of an existing file.

    Never truncates existing target on failure. Preserves original file byte-for-byte
    if write, permissions, or sharing fails.
    Returns SHA256 of published content.
    """
    target_path = Path(target_path)
    if not target_path.is_file():
        raise ArtifactStorageError(
            f"Target file '{target_path}' does not exist for replace",
            code="target_not_found",
            path=str(target_path),
        )

    if expected_sha256 is not None:
        actual_bytes = target_path.read_bytes()
        actual_digest = hashlib.sha256(actual_bytes).hexdigest()
        if actual_digest != expected_sha256:
            raise ArtifactStorageError(
                f"Target file hash mismatch for '{target_path}': expected {expected_sha256}, got {actual_digest}",
                code="stale_target",
                path=str(target_path),
            )

    staged_path, digest = stage_artifact_bytes(target_path, content_bytes)

    # Preserve mode/permissions from original file if possible
    try:
        shutil.copymode(target_path, staged_path)
    except OSError:
        pass

    try:
        # Atomic replace on POSIX and Windows
        os.replace(staged_path, target_path)
    except Exception as ex:
        if staged_path.exists():
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise ArtifactStorageError(
            f"Failed to replace target '{target_path}': {ex}",
            code="atomic_write_failed",
            path=str(target_path),
        ) from ex

    return digest


def cleanup_orphaned_staging(directory: Path, max_age_seconds: float = 3600.0) -> int:
    """Clean up orphaned staging files (.tmp.*) in directory older than max_age_seconds."""
    directory = Path(directory)
    if not directory.is_dir():
        return 0

    removed_count = 0
    now = time.time()

    for p in directory.glob("*.tmp.*"):
        if p.is_file():
            try:
                mtime = p.stat().st_mtime
                # NTFS stamps mtime from another clock than time.time(): a file
                # written a moment ago can read as slightly in the future, a
                # negative age that never reached max_age_seconds=0 (CI flake).
                if max(0.0, now - mtime) >= max_age_seconds:
                    p.unlink(missing_ok=True)
                    removed_count += 1
            except OSError:
                pass

    return removed_count


def verify_published_target_readback(target_path: Path, expected_sha256: str) -> bytes:
    """Verify published target artifact exists and matches expected sha256 checksum."""
    target_path = Path(target_path)
    if not target_path.is_file():
        raise ArtifactStorageError(
            f"Target file '{target_path}' missing during readback verification",
            code="validation_failed",
            path=str(target_path),
        )
    live_bytes = target_path.read_bytes()
    actual_sha256 = hashlib.sha256(live_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ArtifactStorageError(
            f"Readback checksum mismatch for '{target_path}': expected {expected_sha256}, got {actual_sha256}",
            code="validation_failed",
            path=str(target_path),
        )
    return live_bytes
