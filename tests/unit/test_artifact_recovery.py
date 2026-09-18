"""Unit tests for transaction manager, receipt serialization and idempotency (AW-09)."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from deltafuse.core.artifact_policy import AuthorizationContext
from deltafuse.core.artifact_transactions import (
    ArtifactTransactionError,
    TransactionManager,
    compute_receipt_digest,
)


def test_idempotency_same_payload_returns_existing(tmp_path: Path):
    """Same request_id with identical payload reuses existing transaction."""
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

    req_bytes = b'{"operation": "create", "kind": "task"}'
    tx1 = tm.prepare_transaction(
        request_id="req-unique-123",
        raw_request_bytes=req_bytes,
        kind="task",
        target_path=root / "tasks/TASK-001.md",
        previous_sha256=None,
        expected_result_sha256="result_sha_123",
        auth_context=ctx,
    )

    # Retry with SAME payload
    tx2 = tm.prepare_transaction(
        request_id="req-unique-123",
        raw_request_bytes=req_bytes,
        kind="task",
        target_path=root / "tasks/TASK-001.md",
        previous_sha256=None,
        expected_result_sha256="result_sha_123",
        auth_context=ctx,
    )

    assert tx1["transaction_id"] == tx2["transaction_id"]


def test_idempotency_conflict_different_payload_fails(tmp_path: Path):
    """Same request_id with different payload raises idempotency_conflict."""
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

    tm.prepare_transaction(
        request_id="req-conflict-456",
        raw_request_bytes=b'{"payload": "A"}',
        kind="task",
        target_path=root / "tasks/TASK-001.md",
        previous_sha256=None,
        expected_result_sha256="result_sha_A",
        auth_context=ctx,
    )

    # Retry with DIFFERENT payload
    with pytest.raises(ArtifactTransactionError) as exc_info:
        tm.prepare_transaction(
            request_id="req-conflict-456",
            raw_request_bytes=b'{"payload": "B_DIFFERENT"}',
            kind="task",
            target_path=root / "tasks/TASK-001.md",
            previous_sha256=None,
            expected_result_sha256="result_sha_B",
            auth_context=ctx,
        )

    assert exc_info.value.code == "idempotency_conflict"


def test_compute_receipt_digest():
    """Receipt digest is computed deterministically excluding digest field."""
    receipt_dict = {
        "transaction_id": "tx-1",
        "request_id": "req-1",
        "kind": "task",
        "target": "tasks/TASK-001.md",
        "operation": "create",
        "operation_schema_version": "1",
        "storage_schema_identity": "task.schema",
        "storage_schema_hash": "sha256:123",
        "serializer_revision": "1",
        "raw_request_hash": "sha256:req",
        "normalized_payload_hash": "sha256:norm",
        "previous_sha256": None,
        "result_sha256": "sha256:res",
        "changed": True,
        "durable_outcome": "committed",
        "authorization_context": {
            "actor": "worker",
            "work_item": "SLICE-01",
            "stage": "Implement",
            "fingerprint": "fp",
        },
        "validation_scopes": ["schema", "policy"],
    }

    digest1 = compute_receipt_digest(receipt_dict)
    assert isinstance(digest1, str)
    assert digest1.startswith("sha256:")
    assert len(digest1) == 71

    # Digest is unaffected if a dummy 'digest' or 'receipt_sha256' field is present in input dictionary
    dict_with_digest = {**receipt_dict, "digest": "dummy_value", "receipt_sha256": "dummy_value"}
    assert compute_receipt_digest(dict_with_digest) == digest1
