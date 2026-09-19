"""Integration tests for security boundaries, path protection, crash recovery, and authorization (AW-17)."""

import hashlib
import json
from pathlib import Path
import pytest

from deltafuse.core.artifact_patch import apply_artifact_patch, ArtifactPatchError
from deltafuse.core.artifact_policy import (
    create_authorization_context,
    validate_artifact_policy,
    resolve_artifact_path,
    ArtifactPolicyError,
)
from deltafuse.core.artifacts import ArtifactService, ArtifactServiceError
from deltafuse.core.installer import install
from deltafuse.core.scaffold import scaffold_change


def test_security_unauthorized_status_patch_attack(tmp_path: Path, repo_root: Path):
    """Verify that updating protected status fields via patch is rejected."""
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = scaffold_change(tmp_path, "CHG-170", route="code", title="Security Test")

    (change_dir / "slices").mkdir(parents=True, exist_ok=True)
    (change_dir / "slices" / "SLICE-01.md").write_text("---\nid: SLICE-01\nchange: CHG-170\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n", encoding="utf-8")
    (change_dir / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (change_dir / "docs" / "spec" / "core.md").write_text("# Core Spec\n", encoding="utf-8")

    auth = create_authorization_context(actor="worker", work_item="SLICE-01", product_root=change_dir, change_id="CHG-170")
    service = ArtifactService(product_root=change_dir, auth_context=auth)

    # 1. Create task
    task_payload = {
        "title": "Security task",
        "kind": "feature",
        "slice": "SLICE-01",
        "depends_on": [],
        "requirement_delta": "none",
        "spec_refs": ["docs/spec/core.md#REQ-01"],
        "allowed_paths": ["src/app.py"],
        "forbidden_paths": [],
        "context_budget": {"max_tokens": 1000, "max_files": 5},
    }
    service.create(kind="task", identity="TASK-001", semantic_payload=task_payload)
    task_file = change_dir / "tasks" / "TASK-001.md"
    task_sha = hashlib.sha256(task_file.read_bytes()).hexdigest()

    # 2. Attempt patch attack setting /status to "accepted" or "verified"
    patch_attack = {
        "set": [{"path": "/status", "value": "verified"}],
        "remove": [],
    }
    with pytest.raises((ArtifactServiceError, ArtifactPatchError)) as exc_info:
        service.update(kind="task", target="tasks/TASK-001.md", expected_sha256=task_sha, patch=patch_attack)

    assert any(k in str(exc_info.value).lower() for k in ("protected", "immutable", "unauthorized", "invalid", "not allowed"))


def test_security_path_traversal_and_protected_file_attack(tmp_path: Path, repo_root: Path):
    """Verify that path traversal and writing to protected files (.deltafuse) are denied."""
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = scaffold_change(tmp_path, "CHG-171", route="code", title="Path Security Test")

    # 1. Traversal attempt
    with pytest.raises(ArtifactPolicyError, match="traversal"):
        resolve_artifact_path(change_dir, "../../../etc/passwd")

    # 2. Protected .deltafuse file write attempt
    with pytest.raises(ArtifactPolicyError, match="Protected path"):
        resolve_artifact_path(change_dir, ".deltafuse/lock.yaml")


def test_security_malformed_input_rejection_no_side_effects(tmp_path: Path, repo_root: Path):
    """Verify that malformed payloads fail validation before mutating files."""
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = scaffold_change(tmp_path, "CHG-172", route="code", title="Malformed Security Test")

    auth = create_authorization_context(actor="worker", work_item="CLI", product_root=change_dir, change_id="CHG-172")
    service = ArtifactService(product_root=change_dir, auth_context=auth)

    # Payload with invalid property type
    bad_payload = {
        "title": "Bad task",
        "kind": 12345,  # type mismatch (expected string)
        "allowed_paths": ["src/app.py"],
    }
    tasks_dir = change_dir / "tasks"

    with pytest.raises((ArtifactServiceError, ArtifactPolicyError)):
        service.create(kind="task", identity="TASK-002", semantic_payload=bad_payload)

    # Assert no file created
    assert not (tasks_dir / "TASK-002.md").exists()


def test_security_unauthorized_context_denied(tmp_path: Path, repo_root: Path):
    """Verify that ArtifactService denies updates when worker attempts to write Core-only kinds (e.g. evidence)."""
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = scaffold_change(tmp_path, "CHG-173", route="code", title="Auth Security Test")

    auth = create_authorization_context(actor="worker", work_item="CLI", product_root=change_dir, change_id="CHG-173")
    service = ArtifactService(product_root=change_dir, auth_context=auth)
    with pytest.raises(ArtifactPolicyError, match="Worker cannot write Core-only kind"):
        service.create(
            kind="evidence",
            identity="EV-001",
            semantic_payload={
                "title": "Forged evidence",
            },
        )


def test_aw21_reproduce_security_failures(tmp_path: Path):
    """AW-21 Red: Reproduce outside-Change write, missing-context write, and stale-envelope write."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".deltafuse").mkdir()
    (repo_root / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        "  version: 3.1.0\n"
        "  source: deltafuse\n"
        "  content_hash: sha256:17786cb040d1ed3cd5636dd4a6b97453c1b77627\n"
        "workflow:\n"
        "  call_width: wide\n"
        "  auto_accept_decisions: false\n",
        encoding="utf-8",
    )
    change1_dir = repo_root / "docs" / "changes" / "CHG-001"
    change1_dir.mkdir(parents=True)
    outside_file = tmp_path / "outside_target.md"

    auth = create_authorization_context(
        actor="worker",
        work_item="CHG-001",
        product_root=repo_root,
        change_id="CHG-001",
        stage="implement",
    )
    service = ArtifactService(product_root=change1_dir, auth_context=auth)

    # 1. Outside-Change write attempt with absolute path outside product/change root
    with pytest.raises((ArtifactPolicyError, ArtifactServiceError), match="outside|escapes|denied|traversal"):
        service.create(
            kind="task",
            identity=str(outside_file),
            semantic_payload={"kind": "feature", "allowed_paths": []},
            body="evil",
        )
    assert not outside_file.exists()

    # 2. Missing-context write attempt
    service_no_auth = ArtifactService(product_root=change1_dir, auth_context=None)
    with pytest.raises((ArtifactPolicyError, ArtifactServiceError)):
        service_no_auth.create(
            kind="task",
            identity="TASK-100",
            semantic_payload={"kind": "feature", "allowed_paths": []},
        )
    assert not (change1_dir / "tasks" / "TASK-100.md").exists()

    # 3. Stale-envelope / halted stage write attempt
    auth_halted = create_authorization_context(
        actor="worker",
        work_item="CHG-001",
        product_root=repo_root,
        change_id="CHG-001",
        stage="halted",
    )
    service_halted = ArtifactService(product_root=change1_dir, auth_context=auth_halted)
    with pytest.raises((ArtifactPolicyError, ArtifactServiceError), match="halted|stage|policy_denied|unauthorized"):
        service_halted.create(
            kind="task",
            identity="TASK-101",
            semantic_payload={"kind": "feature", "allowed_paths": []},
        )
    assert not (change1_dir / "tasks" / "TASK-101.md").exists()

