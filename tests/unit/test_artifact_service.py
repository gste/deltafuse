"""Unit tests for the typed Artifact Writer service (AW-10)."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from deltafuse.core.artifact_policy import ArtifactPolicyError, AuthorizationContext
from deltafuse.core.artifact_patch import ArtifactPatchError
from deltafuse.core.artifacts import ArtifactService, ArtifactServiceError


@pytest.fixture
def product_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".deltafuse").mkdir()
    (root / "tasks").mkdir()
    (root / "slices").mkdir()
    return root


@pytest.fixture
def auth_context(product_root: Path) -> AuthorizationContext:
    return AuthorizationContext(
        actor="worker",
        work_item="SLICE-01",
        product_root=product_root,
        change_id="CHG-001",
        task_id="TASK-001",
        stage="Implement",
        schema_hash="hash1",
        lock_hash="lock1",
        fingerprint="fp123",
    )


def test_create_task_initializes_core_status_and_rejects_status_override(product_root: Path, auth_context: AuthorizationContext):
    """Caller attempting to pass status in create semantic_payload is rejected with core_owned_field."""
    service = ArtifactService(product_root, auth_context)

    with pytest.raises((ArtifactServiceError, ArtifactPolicyError)) as exc_info:
        service.create(
            kind="task",
            identity="TASK-001",
            semantic_payload={
                "kind": "feature",
                "status": "verified",  # FORBIDDEN!
            },
            body="Task body prose",
        )

    err_code = getattr(exc_info.value, "code", "")
    assert err_code == "core_owned_field" or "status" in str(exc_info.value).lower()


def test_validate_is_strictly_read_only(product_root: Path, auth_context: AuthorizationContext):
    """validate() is strictly read-only and writes zero files to journal, receipts or target."""
    service = ArtifactService(product_root, auth_context)
    task_file = product_root / "tasks" / "TASK-002.md"
    task_content = (
        "---\n"
        "id: TASK-002\n"
        "change: CHG-001\n"
        "slice: SLICE-01\n"
        "kind: feature\n"
        "status: pending\n"
        "depends_on: []\n"
        "requirement_delta: none\n"
        "spec_refs:\n"
        "  - docs/spec/context.md\n"
        "design_ref: null\n"
        "allowed_paths: []\n"
        "forbidden_paths: []\n"
        "context_budget:\n"
        "  max_tokens: 10000\n"
        "  max_files: 5\n"
        "---\n"
        "Body content\n"
    )
    task_file.write_text(task_content, encoding="utf-8")

    journal_dir = product_root / ".deltafuse" / "journal"
    receipts_dir = product_root / ".deltafuse" / "receipts"

    res = service.validate(kind="task", target="tasks/TASK-002.md")

    assert res["valid"] is True
    # Zero journal or receipt directories created
    assert not journal_dir.exists()
    assert not receipts_dir.exists()


def test_create_task_success(product_root: Path, auth_context: AuthorizationContext):
    """Supported artifact created without raw YAML; receipt returned; initial pending status set."""
    service = ArtifactService(product_root, auth_context)

    receipt = service.create(
        kind="task",
        identity="TASK-010",
        semantic_payload={
            "kind": "feature",
            "allowed_paths": ["src/parser.py"],
        },
        body="## Requirements\n- Must parse tokens cleanly.\n",
    )

    assert receipt["kind"] == "task"
    assert receipt["outcome"] == "committed"
    assert receipt["changed"] is True

    created_file = product_root / "tasks" / "TASK-010.md"
    assert created_file.is_file()

    content = created_file.read_text(encoding="utf-8")
    assert "status: pending" in content
    assert "id: TASK-010" in content
    assert "## Requirements" in content


def test_update_slice_success(product_root: Path, auth_context: AuthorizationContext):
    """Update slice title with valid patch, preserving body bytes and draft status."""
    service = ArtifactService(product_root, auth_context)

    create_receipt = service.create(
        kind="slice",
        identity="SLICE-02",
        semantic_payload={
            "title": "Initial slice title",
            "primary_capability": "auth",
            "claims": ["CR-001"],
        },
        body="Opaque slice body prose\n",
    )

    slice_file = product_root / "slices" / "SLICE-02.md"
    expected_hash = hashlib.sha256(slice_file.read_bytes()).hexdigest()

    update_receipt = service.update(
        kind="slice",
        target="slices/SLICE-02.md",
        expected_sha256=expected_hash,
        patch={
            "set": [{"path": "/title", "value": "Updated slice title"}],
        },
    )

    assert update_receipt["outcome"] == "committed"
    assert update_receipt["changed"] is True

    updated_content = slice_file.read_text(encoding="utf-8")
    assert "title: Updated slice title" in updated_content
    assert "status: draft" in updated_content
    assert "Opaque slice body prose" in updated_content


def test_update_status_patch_denied(product_root: Path, auth_context: AuthorizationContext):
    """Patch attempting to alter /status is rejected with core_owned_field."""
    service = ArtifactService(product_root, auth_context)

    service.create(
        kind="slice",
        identity="SLICE-03",
        semantic_payload={
            "title": "Test slice",
            "primary_capability": "auth",
            "claims": ["CR-001"],
        },
    )

    slice_file = product_root / "slices" / "SLICE-03.md"
    expected_hash = hashlib.sha256(slice_file.read_bytes()).hexdigest()

    with pytest.raises((ArtifactServiceError, ArtifactPatchError, ArtifactPolicyError)) as exc_info:
        service.update(
            kind="slice",
            target="slices/SLICE-03.md",
            expected_sha256=expected_hash,
            patch={
                "set": [{"path": "/status", "value": "verified"}],
            },
        )

    err_code = getattr(exc_info.value, "code", "")
    assert err_code == "core_owned_field" or "status" in str(exc_info.value).lower()


def test_failed_validation_leaves_filesystem_and_journal_untouched(product_root: Path, auth_context: AuthorizationContext):
    """Submitting invalid payload during create aborts before transaction journal or target file is written."""
    service = ArtifactService(product_root, auth_context)

    with pytest.raises((ArtifactServiceError, ValueError, KeyError)):
        service.create(
            kind="slice",
            identity="SLICE-99",
            semantic_payload={
                "title": "",  # Invalid: minLength 1 required
                "primary_capability": "auth",
                "claims": ["CR-001"],
            },
        )

    target_file = product_root / "slices" / "SLICE-99.md"
    assert not target_file.exists()

    journal_dir = product_root / ".deltafuse" / "journal"
    assert not journal_dir.exists() or len(list(journal_dir.glob("*"))) == 0


def test_describe_operation(product_root: Path, auth_context: AuthorizationContext):
    """describe() returns kind descriptor schema details without side effects."""
    service = ArtifactService(product_root, auth_context)
    desc = service.describe(kind="task", operation="create")

    assert desc["kind"] == "task"
    assert desc["operation"] == "create"
    assert "allowed_semantic_fields" in desc
