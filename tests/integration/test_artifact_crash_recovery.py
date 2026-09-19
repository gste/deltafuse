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


def test_corrupt_journal_record_stops_recovery_failing_closed(tmp_path: Path):
    """Truncated or corrupt journal records must stop recovery with ArtifactTransactionError instead of disappearing."""
    root = tmp_path / "repo"
    root.mkdir()
    journal_dir = root / ".deltafuse" / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)

    # Write corrupt truncated journal record
    corrupt_file = journal_dir / "tx-corrupt-001.json"
    corrupt_file.write_text('{"transaction_id": "tx-corrupt-001", "state": "prepared"', encoding="utf-8")

    with pytest.raises(ArtifactTransactionError) as exc_info:
        recover_pending_transactions(root)

    assert exc_info.value.code == "corrupt_journal"


def test_receipt_failure_after_publish_preserves_journal_state_and_raises(tmp_path: Path, monkeypatch):
    """Receipt failure after atomic publication raises ArtifactTransactionError and retains published journal state."""
    from deltafuse.core.artifacts import ArtifactService
    from deltafuse.core.artifact_policy import AuthorizationContext

    root = tmp_path / "repo"
    root.mkdir()
    (root / ".deltafuse" / "lock.yaml").parent.mkdir(parents=True, exist_ok=True)
    (root / ".deltafuse" / "lock.yaml").write_text("schema_version: 3\nframework:\n  version: '3.1.0'\n  content_hash: 'sha256:" + ("0" * 64) + "'\n", encoding="utf-8")

    (root / "slices").mkdir(parents=True, exist_ok=True)
    (root / "slices" / "SLICE-01.md").write_text("---\nid: SLICE-01\nchange: CHG-200\nstatus: draft\nprimary_capability: auth\nclaims: [CLAIM-01]\nspec_refs: [docs/spec/auth.md]\n---\n# SLICE-01\n", encoding="utf-8")

    (root / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "spec" / "auth.md").write_text("# Auth Spec\n", encoding="utf-8")



    ctx = AuthorizationContext(
        actor="worker",
        work_item="CHG-200",
        product_root=root,
        change_id="CHG-200",
        task_id="TASK-01",
        stage="Implement",
        schema_hash="hash1",
        lock_hash="lock1",
        fingerprint="fp1",
    )

    svc = ArtifactService(root, auth_context=ctx)

    # Monkeypatch finalize_receipt to simulate a failure AFTER publication
    def mock_finalize_receipt(transaction_id, durable_outcome="committed", changed=True):
        raise ArtifactTransactionError("Disk full during receipt write", code="receipt_write_error")

    monkeypatch.setattr(svc.transaction_mgr, "finalize_receipt", mock_finalize_receipt)

    with pytest.raises(ArtifactTransactionError) as exc_info:
        svc.create(
            kind="task",
            identity="TASK-001",
            semantic_payload={
                "slice": "SLICE-01",
                "kind": "feature",
                "depends_on": [],
                "requirement_delta": "added",
                "spec_refs": ["docs/spec/auth.md#section-1"],
                "allowed_paths": ["src/auth/**"],
                "forbidden_paths": [".deltafuse/**"],
                "context_budget": {"max_tokens": 5000, "max_files": 10},

                "title": "Test Task",
            },
            body="# TASK-001: Test Task\n\nTask body\n",
            request_id="req-receipt-fail-001",
        )



    assert exc_info.value.code in ("receipt_write_error", "receipt_finalization_failed")

    # Invariant: target file was published on disk, and journal record state is 'published'
    target = root / "tasks" / "TASK-001.md"
    assert target.is_file()

    journal_records = list((root / ".deltafuse" / "journal").glob("*.json"))
    assert len(journal_records) == 1
    import json
    rec = json.loads(journal_records[0].read_text(encoding="utf-8"))
    assert rec["state"] == "published"

