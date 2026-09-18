"""Integration tests for crash boundary recovery and durable receipt finalization (AW-09)."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from deltafuse.core.artifact_policy import AuthorizationContext
from deltafuse.core.artifact_transactions import (
    ArtifactTransactionError,
    TransactionManager,
    recover_pending_transactions,
)


def test_crash_before_publish_restores_previous_state(tmp_path: Path):
    """Crash at prepared state (before atomic move): recovery preserves previous target content."""
    root = tmp_path / "repo"
    root.mkdir()
    tm = TransactionManager(root)

    ctx = AuthorizationContext(
        actor="worker",
        work_item="SLICE-01",
        product_root=root,
        change_id="CHG-01",
        task_id="TASK-01",
        stage="Implement",
        schema_hash="hash1",
        lock_hash="lock1",
        fingerprint="fp1",
    )

    target = root / "tasks" / "TASK-001.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    orig_bytes = b"ORIGINAL_TARGET_BYTES"
    target.write_bytes(orig_bytes)
    orig_hash = hashlib.sha256(orig_bytes).hexdigest()

    # Prepare transaction (simulating crash before publish step)
    tm.prepare_transaction(
        request_id="crash-req-001",
        raw_request_bytes=b"NEW_REQUEST",
        kind="task",
        target_path=target,
        previous_sha256=orig_hash,
        expected_result_sha256=hashlib.sha256(b"NEW_BYTES").hexdigest(),
        auth_context=ctx,
    )

    # Run recovery
    outcomes = recover_pending_transactions(root)
    assert len(outcomes) == 1
    assert outcomes[0]["outcome"] == "restored_previous"

    # Invariant: target file on disk is preserved byte-for-byte
    assert target.read_bytes() == orig_bytes


def test_crash_after_publish_finalizes_committed_receipt(tmp_path: Path):
    """Crash after atomic publish (disk matches expected_result_sha256): recovery commits receipt."""
    root = tmp_path / "repo"
    root.mkdir()
    tm = TransactionManager(root)

    ctx = AuthorizationContext(
        actor="worker",
        work_item="SLICE-01",
        product_root=root,
        change_id="CHG-01",
        task_id="TASK-01",
        stage="Implement",
        schema_hash="hash1",
        lock_hash="lock1",
        fingerprint="fp1",
    )

    target = root / "tasks" / "TASK-002.md"
    target.parent.mkdir(parents=True, exist_ok=True)

    new_bytes = b"NEW_PUBLISHED_BYTES_123"
    new_hash = hashlib.sha256(new_bytes).hexdigest()

    tx = tm.prepare_transaction(
        request_id="crash-req-002",
        raw_request_bytes=b"NEW_REQUEST_2",
        kind="task",
        target_path=target,
        previous_sha256=None,
        expected_result_sha256=new_hash,
        auth_context=ctx,
    )

    # Simulate atomic publication succeeded before crash
    target.write_bytes(new_bytes)
    tm.mark_published(tx["transaction_id"])

    # Run recovery
    outcomes = recover_pending_transactions(root)
    assert len(outcomes) == 1
    assert outcomes[0]["outcome"] == "recovered_published"

    # Durable receipt file written under .deltafuse/receipts/
    receipts = list((root / ".deltafuse" / "receipts").glob("*.json"))
    assert len(receipts) == 1


def test_ambiguous_external_edit_stops_recovery_without_overwrite(tmp_path: Path):
    """If target was edited by third party (hash matches neither previous nor expected), recovery stops."""
    root = tmp_path / "repo"
    root.mkdir()
    tm = TransactionManager(root)

    ctx = AuthorizationContext(
        actor="worker",
        work_item="SLICE-01",
        product_root=root,
        change_id="CHG-01",
        task_id="TASK-01",
        stage="Implement",
        schema_hash="hash1",
        lock_hash="lock1",
        fingerprint="fp1",
    )

    target = root / "tasks" / "TASK-003.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"ORIGINAL_BYTES")

    tm.prepare_transaction(
        request_id="crash-req-003",
        raw_request_bytes=b"NEW_REQUEST_3",
        kind="task",
        target_path=target,
        previous_sha256=hashlib.sha256(b"ORIGINAL_BYTES").hexdigest(),
        expected_result_sha256=hashlib.sha256(b"PREPARED_NEW_BYTES").hexdigest(),
        auth_context=ctx,
    )

    # Simulate ambiguous third-party edit on disk
    third_party_bytes = b"THIRD_PARTY_HOSTILE_EDIT_BYTES"
    target.write_bytes(third_party_bytes)

    outcomes = recover_pending_transactions(root)
    assert len(outcomes) == 1
    assert outcomes[0]["outcome"] == "ambiguous_stopped"

    # Third-party file content MUST NOT be overwritten or restored
    assert target.read_bytes() == third_party_bytes
