"""Integration tests for single-file atomic publication primitives (AW-07)."""

from __future__ import annotations

import concurrent.futures
import hashlib
import os
from pathlib import Path
import pytest

from deltafuse.core.artifact_storage import (
    ArtifactStorageError,
    atomic_create,
    atomic_replace,
    cleanup_orphaned_staging,
    stage_artifact_bytes,
)


def test_concurrent_create_race(tmp_path: Path):
    """Two concurrent creates on an absent path: exactly one succeeds."""
    target = tmp_path / "concurrent_test.txt"
    bytes1 = b"CONTENT_FROM_THREAD_1"
    bytes2 = b"CONTENT_FROM_THREAD_2"

    results = []
    errors = []

    def run_create(data: bytes):
        try:
            res = atomic_create(target, data)
            results.append((data, res))
        except ArtifactStorageError as ex:
            errors.append(ex)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(run_create, bytes1)
        f2 = executor.submit(run_create, bytes2)
        concurrent.futures.wait([f1, f2])

    assert len(results) == 1, f"Expected exactly 1 successful create, got {len(results)}"
    assert len(errors) == 1, f"Expected exactly 1 already_exists error, got {len(errors)}"
    assert errors[0].code == "already_exists"

    # Winner's content is present byte-for-byte
    winning_bytes = results[0][0]
    assert target.read_bytes() == winning_bytes


def test_update_failure_preserves_original_file(tmp_path: Path):
    """Failed write/serialization/validation during replace preserves original target."""
    target = tmp_path / "preserve_test.txt"
    original_bytes = b"ORIGINAL_VALID_CONTENT_12345"
    target.write_bytes(original_bytes)
    original_hash = hashlib.sha256(original_bytes).hexdigest()

    # Stale target hash failure
    with pytest.raises(ArtifactStorageError) as exc_info:
        atomic_replace(target, b"NEW_DATA", expected_sha256="wrong_hash_1234567890abcdef")

    assert exc_info.value.code == "stale_target"
    # Essential invariant: original content is untouched (not truncated to 0 bytes)
    assert target.read_bytes() == original_bytes
    assert hashlib.sha256(target.read_bytes()).hexdigest() == original_hash


def test_readback_checksum_validation_failure_aborts(tmp_path: Path, monkeypatch):
    """If staged file readback digest mismatches expected bytes digest, operation aborts."""
    target = tmp_path / "readback_fail.txt"
    content = b"VALID_BYTES"

    # Monkeypatch Path.read_bytes inside stage_artifact_bytes to simulate corruption on readback
    original_read_bytes = Path.read_bytes

    def corrupted_read_bytes(self):
        if self.name.startswith("readback_fail.txt.tmp."):
            return b"CORRUPTED_BYTES"
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", corrupted_read_bytes)

    with pytest.raises(ArtifactStorageError) as exc_info:
        atomic_create(target, content)

    assert exc_info.value.code == "validation_failed"
    assert not target.exists()
    assert list(tmp_path.glob("*.tmp.*")) == []


def test_atomic_create_and_replace_lifecycle(tmp_path: Path):
    """Standard lifecycle: create new file, then replace existing file."""
    target = tmp_path / "lifecycle.txt"
    content_v1 = b"VERSION_1_DATA"
    hash_v1 = atomic_create(target, content_v1)
    assert hash_v1 == hashlib.sha256(content_v1).hexdigest()
    assert target.read_bytes() == content_v1

    # Replace with v2
    content_v2 = b"VERSION_2_DATA"
    hash_v2 = atomic_replace(target, content_v2, expected_sha256=hash_v1)
    assert hash_v2 == hashlib.sha256(content_v2).hexdigest()
    assert target.read_bytes() == content_v2


def test_atomic_create_fails_if_already_exists(tmp_path: Path):
    """atomic_create fails with already_exists if target file already exists."""
    target = tmp_path / "existing.txt"
    target.write_bytes(b"INITIAL")

    with pytest.raises(ArtifactStorageError) as exc_info:
        atomic_create(target, b"NEW_BYTES")

    assert exc_info.value.code == "already_exists"
    assert target.read_bytes() == b"INITIAL"


def test_atomic_replace_fails_if_not_found(tmp_path: Path):
    """atomic_replace fails with target_not_found if target file does not exist."""
    target = tmp_path / "missing.txt"

    with pytest.raises(ArtifactStorageError) as exc_info:
        atomic_replace(target, b"NEW_BYTES")

    assert exc_info.value.code == "target_not_found"
    assert not target.exists()


def test_replace_error_preserves_original_file(tmp_path: Path, monkeypatch):
    """If os.replace fails (e.g., OS permission/sharing error), target remains untouched."""
    target = tmp_path / "sharing_err.txt"
    original_bytes = b"PRESERVE_ME_ON_REPLACE_ERROR"
    target.write_bytes(original_bytes)

    def failing_replace(src, dst):
        raise PermissionError("Simulated Windows file locking / sharing violation")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(ArtifactStorageError) as exc_info:
        atomic_replace(target, b"NEW_UNPUBLISHED_BYTES")

    assert exc_info.value.code == "atomic_write_failed"
    assert target.read_bytes() == original_bytes
    assert list(tmp_path.glob("*.tmp.*")) == []


def test_staging_cleanup_on_success_and_failure(tmp_path: Path):
    """Staging files (.tmp.*) are cleaned up and non-existent after operations."""
    target = tmp_path / "cleanup_test.txt"
    atomic_create(target, b"INITIAL_DATA")

    # Check parent directory for lingering .tmp files
    tmp_files = list(tmp_path.glob("*.tmp.*"))
    assert len(tmp_files) == 0

    # Cleanup helper can remove orphaned temp files
    orphaned = tmp_path / "cleanup_test.txt.tmp.orphaned123"
    orphaned.write_bytes(b"stale")
    removed = cleanup_orphaned_staging(tmp_path, max_age_seconds=0.0)
    assert removed == 1
    assert not orphaned.exists()
