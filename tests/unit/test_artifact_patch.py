"""Unit tests for typed patch application and immutable-field protection (AW-05)."""

from deltafuse import __version__ as FW_VERSION
import pytest
from deltafuse.core.artifact_patch import (
    apply_artifact_patch,
    ArtifactPatchError,
    PatchOutcome,
)


def test_patch_set_and_remove_basic():
    meta = {
        "id": "TASK-001",
        "change": "CHG-001",
        "slice": "SLICE-01",
        "kind": "feature",
        "status": "pending",
        "depends_on": [],
        "requirement_delta": "added",
        "spec_refs": ["docs/spec/auth.md#REQ-01"],
        "design_ref": "docs/design/auth.md",
        "allowed_paths": ["src/auth.py"],
        "forbidden_paths": ["src/billing.py"],
        "context_budget": {"max_tokens": 16000, "max_files": 24},
    }
    patch = {
        "set": [
            {"path": "/requirement_delta", "value": "modified"},
            {"path": "/context_budget/max_tokens", "value": 32000},
        ],
        "remove": ["/design_ref"],
    }
    res = apply_artifact_patch(meta, patch, kind="task")
    assert isinstance(res, PatchOutcome)
    assert res.updated_metadata["requirement_delta"] == "modified"
    assert res.updated_metadata["context_budget"]["max_tokens"] == 32000
    assert "design_ref" not in res.updated_metadata
    assert res.updated_metadata["id"] == "TASK-001"  # preserved


def test_immutable_core_owned_field_rejected():
    meta = {
        "id": "TASK-001",
        "change": "CHG-001",
        "slice": "SLICE-01",
        "kind": "feature",
        "status": "pending",
        "depends_on": [],
        "requirement_delta": "added",
        "spec_refs": ["docs/spec/auth.md#REQ-01"],
        "allowed_paths": ["src/auth.py"],
        "forbidden_paths": [],
        "context_budget": {"max_tokens": 16000, "max_files": 24},
    }
    patch = {"set": [{"path": "/status", "value": "verified"}]}
    with pytest.raises(ArtifactPatchError, match="Core-owned"):
        apply_artifact_patch(meta, patch, kind="task")


def test_array_index_edit_rejected():
    meta = {
        "id": "TASK-001",
        "change": "CHG-001",
        "slice": "SLICE-01",
        "kind": "feature",
        "status": "pending",
        "depends_on": [],
        "requirement_delta": "added",
        "spec_refs": ["docs/spec/auth.md#REQ-01"],
        "allowed_paths": ["src/auth.py"],
        "forbidden_paths": [],
        "context_budget": {"max_tokens": 16000, "max_files": 24},
    }
    patch = {"set": [{"path": "/spec_refs/0", "value": "docs/spec/auth.md#REQ-02"}]}
    with pytest.raises(ArtifactPatchError, match="array index"):
        apply_artifact_patch(meta, patch, kind="task")


def test_ancestor_descendant_overlap_rejected():
    meta = {
        "schema_version": 3,
        "id": "CHG-001",
        "title": "Title",
        "status": "normalized",
        "framework": {"version": FW_VERSION, "content_hash": "sha256:" + ("0" * 64)},
        "intent": "bugfix",
        "risk": "low",
        "source": {"request": "request.md", "intake_refs": []},
        "deltas": [],
        "slices": [],
        "decisions": [],
        "tasks": [],
    }
    patch = {
        "set": [
            {"path": "/source", "value": {"request": "new.md"}},
            {"path": "/source/request", "value": "other.md"},
        ]
    }
    with pytest.raises(ArtifactPatchError, match="overlapping"):
        apply_artifact_patch(meta, patch, kind="change")


def test_unrelated_extension_fields_preserved():
    meta = {
        "change": "CHG-001",
        "claims": {},
        "custom_extension": "preserved_val",
    }
    patch = {"set": [{"path": "/claims", "value": {"CR-001": {"primary_capability": "auth"}}}]}
    res = apply_artifact_patch(meta, patch, kind="routing")
    assert res.updated_metadata["custom_extension"] == "preserved_val"


def test_body_preserved_unless_replaced():
    meta = {
        "id": "TASK-001",
        "change": "CHG-001",
        "slice": "SLICE-01",
        "kind": "feature",
        "status": "pending",
        "depends_on": [],
        "requirement_delta": "added",
        "spec_refs": ["docs/spec/auth.md#REQ-01"],
        "allowed_paths": ["src/auth.py"],
        "forbidden_paths": [],
        "context_budget": {"max_tokens": 16000, "max_files": 24},
    }
    patch = {"set": [{"path": "/requirement_delta", "value": "modified"}]}
    original_body = "## Task Body\n\nPreserved content.\n"
    res = apply_artifact_patch(meta, patch, kind="task", body=original_body)
    assert res.updated_body == original_body

    res_replaced = apply_artifact_patch(meta, patch, kind="task", body=original_body, body_replacement="## New Body\n")
    assert res_replaced.updated_body == "## New Body\n"
