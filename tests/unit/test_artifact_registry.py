"""Unit tests for ArtifactRegistry schema resolution and structured validation (AW-03)."""

from pathlib import Path
import pytest

from deltafuse.core.artifact_registry import (
    ArtifactRegistry,
    ArtifactRegistryError,
    ValidationResult,
)


def test_registry_initialization_and_descriptors():
    registry = ArtifactRegistry()
    desc = registry.get_descriptor("task")
    assert desc["kind"] == "task"
    assert "create" in desc["allowed_operations"]
    assert "status" in desc["core_owned_fields"]


def test_core_owned_field_in_create_payload_rejected():
    registry = ArtifactRegistry()
    res = registry.validate_operation_input(
        kind="task",
        operation="create",
        semantic_payload={"status": "verified", "title": "Sneaky Task"},
    )
    assert not res.valid
    assert any(d.code == "core_owned_field" for d in res.diagnostics)


def test_update_patch_core_owned_field_rejected():
    registry = ArtifactRegistry()
    res = registry.validate_operation_input(
        kind="task",
        operation="update",
        patch={
            "set": [{"path": "/status", "value": "verified"}],
            "remove": ["/id"],
        },
    )
    assert not res.valid
    assert len(res.diagnostics) == 2
    assert all(d.code == "core_owned_field" for d in res.diagnostics)


def test_unsupported_kind_rejected():
    registry = ArtifactRegistry()
    with pytest.raises(ArtifactRegistryError, match="Unsupported kind"):
        registry.get_descriptor("nonexistent_kind")


def test_schema_hash_mismatch_or_corrupt_bundle_rejected(tmp_path: Path):
    registry = ArtifactRegistry(product_root=tmp_path)
    with pytest.raises(ArtifactRegistryError, match="mismatch"):
        registry.get_storage_schema("task", expected_hash="sha256:" + ("0" * 64))


def test_structured_diagnostics_format():
    registry = ArtifactRegistry()
    invalid_task = {
        "id": "INVALID-ID",
        "change": "CHG-001",
        "slice": "SLICE-01",
        "kind": "feature",
        "status": "pending",
        "depends_on": [],
        "requirement_delta": "added",
        "spec_refs": ["docs/spec/auth.md#REQ-01"],
        "allowed_paths": ["src/auth.py"],
        "forbidden_paths": ["src/billing.py"],
        "context_budget": {"max_tokens": 16000, "max_files": 24},
    }
    res = registry.validate_storage_schema("task", invalid_task)
    assert not res.valid
    assert len(res.diagnostics) > 0
    diag = res.diagnostics[0]
    assert hasattr(diag, "code")
    assert hasattr(diag, "path")
    assert hasattr(diag, "message")


def test_reference_validation_scope(tmp_path: Path):
    registry = ArtifactRegistry()
    task_payload = {
        "id": "TASK-001",
        "change": "CHG-001",
        "slice": "SLICE-99",  # missing
        "kind": "feature",
        "status": "pending",
        "depends_on": [],
        "requirement_delta": "added",
        "spec_refs": [],
        "allowed_paths": ["src/auth.py"],
        "forbidden_paths": [],
        "context_budget": {"max_tokens": 16000, "max_files": 24},
    }
    res = registry.validate_references("task", task_payload, change_dir=tmp_path)
    assert not res.valid
    assert any(d.code == "missing_reference" for d in res.diagnostics)
    assert any(s["scope"] == "whole_gate" and s["status"] == "not_evaluated" for s in res.scopes)


def test_valid_legacy_extension_fields_supported():
    registry = ArtifactRegistry()
    valid_routing_ext = {
        "change": "CHG-001",
        "claims": {},
        "custom_extension": "supported",
    }
    res = registry.validate_storage_schema("routing", valid_routing_ext)
    assert res.valid
