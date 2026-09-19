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
    from deltafuse.core.assets import get_installed_lock_hash
    lock_hash = get_installed_lock_hash()
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".deltafuse").mkdir()
    (root / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        "  version: 3.1.0\n"
        "  source: deltafuse\n"
        f"  content_hash: {lock_hash}\n"
        "workflow:\n"
        "  call_width: wide\n"
        "  auto_accept_decisions: false\n",
        encoding="utf-8",
    )
    (root / "change.yaml").write_text(
        "schema_version: 3\nid: CHG-001\ntitle: Test Change\nstatus: implement\n",
        encoding="utf-8",
    )
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

    # Set up referenced files
    slice_file = product_root / "slices" / "SLICE-01.md"
    slice_file.write_text("---\nid: SLICE-01\nchange: CHG-001\ntitle: Auth Slice\nstatus: draft\nprimary_capability: auth\nclaims:\n  - CR-001\n---\nSlice body\n", encoding="utf-8")
    spec_file = product_root / "docs" / "spec" / "context.md"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text("# Spec Context\n", encoding="utf-8")

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

    # Set up prerequisite slice and spec files
    slice_file = product_root / "slices" / "SLICE-01.md"
    slice_file.write_text("---\nid: SLICE-01\nchange: CHG-001\ntitle: Auth Slice\nstatus: draft\nprimary_capability: auth\nclaims:\n  - CR-001\n---\nSlice body\n", encoding="utf-8")
    spec_file = product_root / "docs" / "spec" / "overview.md"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text("# Spec Overview\n", encoding="utf-8")

    receipt = service.create(
        kind="task",
        identity="TASK-010",
        semantic_payload={
            "title": "Parse tokens cleanly",
            "kind": "feature",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": ["src/parser.py"],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 100000, "max_files": 20},
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


def test_reproduce_finding_2_empty_payload_rejected(product_root: Path, auth_context: AuthorizationContext):
    """AW-22 Red: Empty payload in task create must be rejected rather than committing invented semantics."""
    service = ArtifactService(product_root, auth_context)

    with pytest.raises((ArtifactServiceError, ArtifactPolicyError)) as exc_info:
        service.create(
            kind="task",
            identity="TASK-001",
            semantic_payload={},
            body="Task body prose",
        )

    err = exc_info.value
    assert getattr(err, "code", "") in ("schema_validation_failed", "required_property_missing", "missing_core_context")


def test_create_task_omitted_required_fields_rejected(product_root: Path, auth_context: AuthorizationContext):
    """AW-22 Red: Omitting title, kind, or spec_refs individually must be rejected."""
    service = ArtifactService(product_root, auth_context)

    # Omit kind
    with pytest.raises((ArtifactServiceError, ArtifactPolicyError)) as exc_info:
        service.create(
            kind="task",
            identity="TASK-002",
            semantic_payload={
                "title": "Task 002",
                "spec_refs": ["docs/spec/overview.md"],
                "allowed_paths": [],
                "forbidden_paths": [],
                "context_budget": {"max_tokens": 1000, "max_files": 2},
                "depends_on": [],
                "requirement_delta": "none",
            },
        )
    assert getattr(exc_info.value, "code", "") in ("schema_validation_failed", "required_property_missing")

    # Omit title (and body has no title header)
    with pytest.raises((ArtifactServiceError, ArtifactPolicyError)) as exc_info:
        service.create(
            kind="task",
            identity="TASK-003",
            semantic_payload={
                "kind": "feature",
                "spec_refs": ["docs/spec/overview.md"],
                "allowed_paths": [],
                "forbidden_paths": [],
                "context_budget": {"max_tokens": 1000, "max_files": 2},
                "depends_on": [],
                "requirement_delta": "none",
            },
            body="No title header here",
        )
    assert getattr(exc_info.value, "code", "") in ("schema_validation_failed", "required_property_missing")


def test_create_task_missing_core_context_rejected(product_root: Path):
    """AW-22 Red: Creating a task without Core authorization context or missing change_id/work_item must fail."""
    # Service without auth_context
    service_no_auth = ArtifactService(product_root, None)
    with pytest.raises((ArtifactServiceError, ArtifactPolicyError)) as exc_info:
        service_no_auth.create(
            kind="task",
            identity="TASK-005",
            semantic_payload={
                "title": "Task 005",
                "kind": "feature",
                "spec_refs": ["docs/spec/overview.md"],
                "allowed_paths": [],
                "forbidden_paths": [],
                "context_budget": {"max_tokens": 1000, "max_files": 2},
                "depends_on": [],
                "requirement_delta": "none",
            },
        )
    assert getattr(exc_info.value, "code", "") in ("policy_denied", "missing_core_context", "null_authorization_context")

    # Service with invalid auth_context (missing change_id)
    invalid_auth = AuthorizationContext(
        actor="worker",
        work_item="SLICE-01",
        product_root=product_root,
        change_id="",  # Missing change_id!
        task_id="TASK-005",
        stage="Implement",
        schema_hash="hash1",
        lock_hash="lock1",
        fingerprint="fp123",
    )
    service_bad_auth = ArtifactService(product_root, invalid_auth)
    with pytest.raises((ArtifactServiceError, ArtifactPolicyError)) as exc_info:
        service_bad_auth.create(
            kind="task",
            identity="TASK-005",
            semantic_payload={
                "title": "Task 005",
                "kind": "feature",
                "spec_refs": ["docs/spec/overview.md"],
                "allowed_paths": [],
                "forbidden_paths": [],
                "context_budget": {"max_tokens": 1000, "max_files": 2},
                "depends_on": [],
                "requirement_delta": "none",
            },
        )
    assert getattr(exc_info.value, "code", "") in ("missing_core_context", "policy_denied", "missing_change_authority")


def test_reproduce_finding_4_malformed_lock_and_receipt_provenance(tmp_path: Path):
    """AW-24 Red: Malformed lock must deny creation; receipts must contain true byte hashes and real timestamp."""
    from deltafuse.core.artifact_registry import ArtifactRegistryError

    root = tmp_path / "repo"
    root.mkdir()
    (root / ".deltafuse").mkdir()
    (root / "slices").mkdir()
    (root / "tasks").mkdir()
    (root / "change.yaml").write_text("schema_version: 3\nid: CHG-001\ntitle: Test Change\nstatus: implement\n", encoding="utf-8")

    # Part A: Malformed lock.yaml (unsupported schema_version: 99)
    lock_file = root / ".deltafuse" / "lock.yaml"
    lock_file.write_text("schema_version: 99\nframework:\n  version: 3.1.0\n", encoding="utf-8")

    auth = AuthorizationContext(
        actor="worker",
        work_item="SLICE-01",
        product_root=root,
        change_id="CHG-001",
        task_id="TASK-001",
        stage="Implement",
        schema_hash="hash1",
        lock_hash="lock1",
        fingerprint="fp123",
    )
    service = ArtifactService(root, auth)

    slice_file = root / "slices" / "SLICE-01.md"
    slice_file.write_text("---\nid: SLICE-01\nchange: CHG-001\ntitle: Auth Slice\nstatus: draft\nprimary_capability: auth\nclaims:\n  - CR-001\n---\nSlice body\n", encoding="utf-8")
    spec_file = root / "docs" / "spec" / "overview.md"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text("# Spec Overview\n", encoding="utf-8")

    # Malformed lock must deny create!
    with pytest.raises((ArtifactServiceError, ArtifactRegistryError, ArtifactPolicyError)):
        service.create(
            kind="task",
            identity="TASK-001",
            semantic_payload={
                "title": "Parse tokens cleanly",
                "kind": "feature",
                "depends_on": [],
                "requirement_delta": "none",
                "spec_refs": ["docs/spec/overview.md"],
                "allowed_paths": ["src/parser.py"],
                "forbidden_paths": [],
                "context_budget": {"max_tokens": 100000, "max_files": 20},
            },
            body="Task body prose\n",
        )

    # Part B: Repair lock.yaml to valid content
    from deltafuse.core.assets import get_installed_lock_hash
    lock_file.write_text(
        "schema_version: 3\n"
        "framework:\n"
        "  version: 3.1.0\n"
        "  source: deltafuse\n"
        f"  content_hash: {get_installed_lock_hash()}\n"
        "workflow:\n"
        "  call_width: wide\n"
        "  auto_accept_decisions: false\n",
        encoding="utf-8",
    )

    receipt = service.create(
        kind="task",
        identity="TASK-001",
        semantic_payload={
            "title": "Parse tokens cleanly",
            "kind": "feature",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": ["src/parser.py"],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 100000, "max_files": 20},
        },
        body="Task body prose\n",
    )

    # Receipt schema hashes must NOT be zeros ("sha256:" + ("0"*64))
    op_hash = receipt["operation_schema"]["content_hash"]
    st_hash = receipt["storage_schema"]["content_hash"]
    assert op_hash != "sha256:" + ("0" * 64), f"operation_schema content_hash was zeroed: {op_hash}"
    assert st_hash != "sha256:" + ("0" * 64), f"storage_schema content_hash was zeroed: {st_hash}"

    # Timestamp must NOT be fixed "2026-09-18T08:00:00Z"
    ts = receipt["timestamp"]
    assert ts != "2026-09-18T08:00:00Z", f"timestamp was fixed: {ts}"


def test_reproduce_finding_5_update_idempotency_and_create_body_conflict(product_root: Path, auth_context: AuthorizationContext):
    """Reproduce Finding 5:
    1. Identical update retry must return original receipt instead of failing stale_target.
    2. Create with same request_id but changed body must raise idempotency_conflict instead of returning old receipt.
    """
    from deltafuse.core.artifact_transactions import ArtifactTransactionError

    service = ArtifactService(product_root, auth_context)

    # Set up prerequisite files for task creation
    slice_file = product_root / "slices" / "SLICE-01.md"
    slice_file.write_text("---\nid: SLICE-01\nchange: CHG-001\ntitle: Auth Slice\nstatus: draft\nprimary_capability: auth\nclaims:\n  - CR-001\n---\nSlice body\n", encoding="utf-8")
    spec_file = product_root / "docs" / "spec" / "overview.md"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text("# Spec Overview\n", encoding="utf-8")

    # Part 1: Create a task artifact first
    cr_receipt = service.create(
        kind="task",
        identity="TASK-010",
        semantic_payload={
            "title": "Initial Task Title",
            "kind": "feature",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": ["src/app.py"],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 10000, "max_files": 5},
        },
        body="# TASK-010: Initial Task Title\n\nInitial Body\n",
        request_id="req-create-10",
    )

    # Test Part 2: Create retry with SAME request_id but CHANGED body
    with pytest.raises(ArtifactTransactionError) as exc_info:
        service.create(
            kind="task",
            identity="TASK-010",
            semantic_payload={
                "title": "Initial Task Title",
                "kind": "feature",
                "depends_on": [],
                "requirement_delta": "none",
                "spec_refs": ["docs/spec/overview.md"],
                "allowed_paths": ["src/app.py"],
                "forbidden_paths": [],
                "context_budget": {"max_tokens": 10000, "max_files": 5},
            },
            body="# TASK-010: Initial Task Title\n\nCHANGED Body Content\n",
            request_id="req-create-10",
        )
    assert exc_info.value.code == "idempotency_conflict"

    # Now test Part 1: Update retry idempotency
    target_file = product_root / "tasks" / "TASK-010.md"
    h0 = hashlib.sha256(target_file.read_bytes()).hexdigest()

    up_receipt1 = service.update(
        kind="task",
        target="tasks/TASK-010.md",
        expected_sha256=h0,
        patch={"set": [{"path": "/kind", "value": "refactor"}]},
        request_id="req-update-10",
    )
    assert up_receipt1["changed"] is True

    # Retry the EXACT SAME update request (with expected_sha256=h0 and request_id="req-update-10")
    up_receipt2 = service.update(
        kind="task",
        target="tasks/TASK-010.md",
        expected_sha256=h0,
        patch={"set": [{"path": "/kind", "value": "refactor"}]},
        request_id="req-update-10",
    )
    assert up_receipt2["transaction_id"] == up_receipt1["transaction_id"]
    assert up_receipt2["changed"] is True


def test_update_retry_with_unrelated_later_target_edit(product_root: Path, auth_context: AuthorizationContext):
    """Returning historical receipt for identical retry must not claim live file is unchanged or overwrite live edit."""
    service = ArtifactService(product_root, auth_context)

    slice_file = product_root / "slices" / "SLICE-01.md"
    slice_file.write_text("---\nid: SLICE-01\nchange: CHG-001\ntitle: Auth Slice\nstatus: draft\nprimary_capability: auth\nclaims:\n  - CR-001\n---\nSlice body\n", encoding="utf-8")
    spec_file = product_root / "docs" / "spec" / "overview.md"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text("# Spec Overview\n", encoding="utf-8")

    cr_receipt = service.create(
        kind="task",
        identity="TASK-020",
        semantic_payload={
            "title": "Task 20 Title",
            "kind": "feature",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 10000, "max_files": 5},
        },
        body="# TASK-020: Task 20 Title\n\nBody V1\n",
        request_id="req-cr-20",
    )

    target_file = product_root / "tasks" / "TASK-020.md"
    h0 = hashlib.sha256(target_file.read_bytes()).hexdigest()

    up_receipt1 = service.update(
        kind="task",
        target="tasks/TASK-020.md",
        expected_sha256=h0,
        patch={"set": [{"path": "/kind", "value": "refactor"}]},
        request_id="req-up-20",
    )
    assert up_receipt1["changed"] is True

    # External edit to target file after update
    target_file.write_text(target_file.read_text(encoding="utf-8") + "\n# Unrelated external append\n", encoding="utf-8")
    bytes_after_external = target_file.read_bytes()

    # Retry the original update request
    up_receipt2 = service.update(
        kind="task",
        target="tasks/TASK-020.md",
        expected_sha256=h0,
        patch={"set": [{"path": "/kind", "value": "refactor"}]},
        request_id="req-up-20",
    )
    assert up_receipt2["transaction_id"] == up_receipt1["transaction_id"]
    assert up_receipt2["changed"] is True
    # Verify live file on disk was NOT overwritten or reverted
    assert target_file.read_bytes() == bytes_after_external


def test_noop_update_retry_and_conflict_checks(product_root: Path, auth_context: AuthorizationContext):
    """No-op update retry returns changed=False; changing patch or expected_sha256 raises idempotency_conflict."""
    from deltafuse.core.artifact_transactions import ArtifactTransactionError

    service = ArtifactService(product_root, auth_context)

    slice_file = product_root / "slices" / "SLICE-01.md"
    slice_file.write_text("---\nid: SLICE-01\nchange: CHG-001\ntitle: Auth Slice\nstatus: draft\nprimary_capability: auth\nclaims:\n  - CR-001\n---\nSlice body\n", encoding="utf-8")
    spec_file = product_root / "docs" / "spec" / "overview.md"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text("# Spec Overview\n", encoding="utf-8")

    service.create(
        kind="task",
        identity="TASK-030",
        semantic_payload={
            "title": "Task 30 Title",
            "kind": "feature",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 10000, "max_files": 5},
        },
        body="# TASK-030: Task 30 Title\n\nBody V1\n",
        request_id="req-cr-30",
    )

    target_file = product_root / "tasks" / "TASK-030.md"
    h0 = hashlib.sha256(target_file.read_bytes()).hexdigest()

    # No-op update
    noop_receipt1 = service.update(
        kind="task",
        target="tasks/TASK-030.md",
        expected_sha256=h0,
        patch={"set": []},
        request_id="req-noop-30",
    )
    assert noop_receipt1["changed"] is False
    assert noop_receipt1["outcome"] == "unchanged"

    # Retry no-op update
    noop_receipt2 = service.update(
        kind="task",
        target="tasks/TASK-030.md",
        expected_sha256=h0,
        patch={"set": []},
        request_id="req-noop-30",
    )
    assert noop_receipt2["transaction_id"] == noop_receipt1["transaction_id"]
    assert noop_receipt2["changed"] is False

    # Reuse request_id with different patch
    with pytest.raises(ArtifactTransactionError) as exc_info:
        service.update(
            kind="task",
            target="tasks/TASK-030.md",
            expected_sha256=h0,
            patch={"set": [{"path": "/kind", "value": "refactor"}]},
            request_id="req-noop-30",
        )
    assert exc_info.value.code == "idempotency_conflict"


def test_aw34_missing_slice_selection_and_malformed_slice_rejection(tmp_path: Path):
    """AW-34 Red: Unselected slice must not be inferred from directory order, and malformed/wrong-identity/wrong-change references must reject."""
    from deltafuse.core.assets import get_installed_lock_hash
    lock_hash = get_installed_lock_hash()
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".deltafuse").mkdir()
    (root / ".deltafuse" / "config.yaml").write_text("framework_version: 3.1.0\n", encoding="utf-8")
    (root / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        "  version: 3.1.0\n"
        "  source: deltafuse\n"
        f"  content_hash: {lock_hash}\n",
        encoding="utf-8",
    )
    (root / "docs" / "spec").mkdir(parents=True)
    (root / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")
    (root / "change.yaml").write_text("schema_version: 3\nid: CHG-001\ntitle: Test Change\nstatus: implement\n", encoding="utf-8")

    slices_dir = root / "slices"
    slices_dir.mkdir()

    # SLICE-01: Malformed frontmatter
    (slices_dir / "SLICE-01.md").write_text("---\nid: SLICE-01\nmalformed_field: [unclosed bracket\n---\n# Slice 01\n", encoding="utf-8")
    # SLICE-02: Valid slice
    (slices_dir / "SLICE-02.md").write_text("---\nid: SLICE-02\nchange: CHG-001\nstatus: active\n---\n# Slice 02\n", encoding="utf-8")
    # SLICE-03: Slice belonging to a different change
    (slices_dir / "SLICE-03.md").write_text("---\nid: SLICE-03\nchange: CHG-999\nstatus: active\n---\n# Slice 03\n", encoding="utf-8")

    auth = AuthorizationContext(
        actor="worker",
        work_item="CHG-001",  # Not a SLICE-* identifier!
        product_root=root,
        change_id="CHG-001",
        task_id="TASK-010",
        stage="Implement",
        schema_hash="hash",
        lock_hash="lock",
        fingerprint="fp",
    )
    service = ArtifactService(root, auth)

    # 1. Missing slice selection in payload and auth context must be rejected (no first-file inference)
    with pytest.raises((ArtifactServiceError, ArtifactPolicyError)) as exc_info:
        service.create(
            kind="task",
            identity="TASK-010",
            semantic_payload={
                "title": "Task 010",
                "kind": "feature",
                "spec_refs": ["docs/spec/overview.md"],
                "allowed_paths": [],
                "forbidden_paths": [],
                "context_budget": {"max_tokens": 1000, "max_files": 2},
                "depends_on": [],
                "requirement_delta": "none",
            },
        )
    assert getattr(exc_info.value, "code", "") in ("missing_core_context", "policy_denied", "missing_reference")

    # 2. Explicit selection of malformed slice SLICE-01 must reject
    with pytest.raises(ArtifactServiceError) as exc_info2:
        service.create(
            kind="task",
            identity="TASK-011",
            semantic_payload={
                "title": "Task 011",
                "slice": "SLICE-01",
                "kind": "feature",
                "spec_refs": ["docs/spec/overview.md"],
                "allowed_paths": [],
                "forbidden_paths": [],
                "context_budget": {"max_tokens": 1000, "max_files": 2},
                "depends_on": [],
                "requirement_delta": "none",
            },
        )
    assert exc_info2.value.code == "missing_reference"

    # 3. Explicit selection of slice belonging to wrong Change CHG-999 must reject
    with pytest.raises(ArtifactServiceError) as exc_info3:
        service.create(
            kind="task",
            identity="TASK-012",
            semantic_payload={
                "title": "Task 012",
                "slice": "SLICE-03",
                "kind": "feature",
                "spec_refs": ["docs/spec/overview.md"],
                "allowed_paths": [],
                "forbidden_paths": [],
                "context_budget": {"max_tokens": 1000, "max_files": 2},
                "depends_on": [],
                "requirement_delta": "none",
            },
        )
    assert exc_info3.value.code == "missing_reference"
