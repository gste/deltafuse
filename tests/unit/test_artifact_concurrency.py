"""Unit tests for optimistic concurrency and authority recheck (AW-08)."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from deltafuse.core.artifact_lock import (
    ArtifactLockError,
    check_noop_mutation,
    revalidate_authority,
    validate_expected_hash,
)
from deltafuse.core.artifact_policy import AuthorizationContext


def test_validate_expected_hash_success(tmp_path: Path):
    """Whole-file expected hash matching target content passes validation."""
    target = tmp_path / "target.md"
    content = b"---\nid: TASK-001\n---\nBody text with comments # comment\n"
    target.write_bytes(content)
    expected_hash = hashlib.sha256(content).hexdigest()

    # Must pass without raising
    validate_expected_hash(target, expected_hash)


def test_validate_expected_hash_mismatch_fails(tmp_path: Path):
    """Whole-file expected hash mismatch (body/metadata changed) raises stale_target."""
    target = tmp_path / "target.md"
    content = b"---\nid: TASK-001\n---\nBody text\n"
    target.write_bytes(content)

    wrong_hash = hashlib.sha256(b"DIFFERENT_BODY").hexdigest()
    with pytest.raises(ArtifactLockError) as exc_info:
        validate_expected_hash(target, wrong_hash)

    assert exc_info.value.code == "stale_target"


def test_validate_expected_hash_missing_file(tmp_path: Path):
    """Missing target file raises stale_target / target_not_found."""
    target = tmp_path / "nonexistent.md"
    with pytest.raises(ArtifactLockError) as exc_info:
        validate_expected_hash(target, "0" * 64)

    assert exc_info.value.code in ("stale_target", "target_not_found")


def test_revalidate_authority_revoked_fails(tmp_path: Path):
    """Authority context revalidation fails if authority fingerprint changes before commit."""
    root = tmp_path / "repo"
    root.mkdir()

    ctx1 = AuthorizationContext(
        actor="worker",
        work_item="SLICE-01",
        product_root=root,
        change_id="CHG-01",
        task_id="TASK-01",
        stage="Implement",
        schema_hash="hash1",
        lock_hash="lock1",
        fingerprint="fingerprint_valid_123",
    )

    # Authority provider returns updated context with different fingerprint (revoked/changed)
    def current_auth_fn():
        return AuthorizationContext(
            actor="worker",
            work_item="SLICE-01",
            product_root=root,
            change_id="CHG-01",
            task_id="TASK-01",
            stage="Implement",
            schema_hash="hash1",
            lock_hash="lock1",
            fingerprint="fingerprint_REVOKED_456",
        )

    with pytest.raises(ArtifactLockError) as exc_info:
        revalidate_authority(ctx1, current_auth_fn)

    assert exc_info.value.code == "authority_revoked"


def test_check_noop_mutation():
    """Identical candidate bytes identified as no-op."""
    raw = b"---\ntitle: Hello\n---\nBody content\n"
    assert check_noop_mutation(raw, raw) is True
    assert check_noop_mutation(raw, b"---\ntitle: World\n---\nBody content\n") is False
