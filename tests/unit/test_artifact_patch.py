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


# AW-46 supplies the executable invariant behind AW39-R3: "Verify JSON Pointer escaping
# and missing nested paths; do not skip a failed lookup or substitute top-level deletion
# checks for nested removals." Routing claims are schema-closed, so the escaped tokens
# are exercised in a nested extension container that the routing schema permits.

SLASH_KEY = "a/b"
TILDE_KEY = "m~n"


def _routing_doc(notes):
    return {
        "change": "CHG-001",
        "claims": {"CR-001": {"primary_capability": "core"}},
        "extension-notes": notes,
    }


def test_aw46_escaped_pointer_set_writes_decoded_nested_keys():
    """AW39-R3: ~1 and ~0 must be decoded before the patch addresses a key."""
    outcome = apply_artifact_patch(
        _routing_doc({SLASH_KEY: {TILDE_KEY: "before", "summary": "keep"}}),
        {"set": [{"path": "/extension-notes/a~1b/m~0n", "value": "after"}]},
        kind="routing",
    )
    notes = outcome.updated_metadata["extension-notes"]
    assert list(notes) == [SLASH_KEY], f"escaped pointer created a literal key instead of '{SLASH_KEY}': {notes}"
    assert notes[SLASH_KEY][TILDE_KEY] == "after"
    assert notes[SLASH_KEY]["summary"] == "keep", "sibling of the escaped target must survive the set"
    assert outcome.changed is True and outcome.applied_ops_count == 1


def test_aw46_escaped_pointer_unescaping_follows_rfc6901_order():
    """AW39-R3: ~01 means a literal '~1' key; a swapped replace order resolves it to 'a/b'."""
    outcome = apply_artifact_patch(
        _routing_doc({"a~1b": {"summary": "target"}}),
        {"set": [{"path": "/extension-notes/a~01b/summary", "value": "updated"}]},
        kind="routing",
    )
    notes = outcome.updated_metadata["extension-notes"]
    assert notes["a~1b"]["summary"] == "updated", f"'~01' did not decode to '~1': {notes}"
    assert "a/b" not in notes, f"'~01' was decoded as '~1' then '/', which reorders RFC 6901 unescaping: {notes}"


def test_aw46_escaped_pointer_remove_targets_only_the_nested_key():
    """AW39-R3: a nested removal may not be satisfied by a top-level or same-named key."""
    document = _routing_doc({SLASH_KEY: {TILDE_KEY: "drop", "summary": "keep"}, "other": {TILDE_KEY: "untouched"}})
    outcome = apply_artifact_patch(
        document, {"remove": ["/extension-notes/a~1b/m~0n"]}, kind="routing"
    )
    notes = outcome.updated_metadata["extension-notes"]
    assert SLASH_KEY in notes, "the parent container of a nested removal must remain"
    assert notes[SLASH_KEY] == {"summary": "keep"}, f"nested removal over- or under-matched: {notes}"
    assert notes["other"] == {TILDE_KEY: "untouched"}, "an equally named key elsewhere must not be deleted"
    assert outcome.applied_ops_count == 1


def test_aw46_escaped_pointer_does_not_match_a_literal_tilde_key():
    """AW39-R3: '~1' addresses key 'a/b', never the literal text 'a~1b' on disk."""
    document = _routing_doc({"a~1b": {"summary": "keep"}})
    with pytest.raises(ArtifactPatchError) as excinfo:
        apply_artifact_patch(document, {"remove": ["/extension-notes/a~1b"]}, kind="routing")
    assert excinfo.value.code == "remove_target_missing"
    assert excinfo.value.path == "/extension-notes/a~1b"
    assert document["extension-notes"] == {"a~1b": {"summary": "keep"}}, "denial must not mutate the document"


def test_aw46_missing_nested_path_fails_loudly_instead_of_being_skipped():
    """AW39-R3: a missing nested path is a failed lookup, not a silent no-op."""
    document = _routing_doc({SLASH_KEY: {"summary": "keep"}})
    with pytest.raises(ArtifactPatchError) as excinfo:
        apply_artifact_patch(document, {"remove": ["/extension-notes/a~1b/m~0n"]}, kind="routing")
    assert excinfo.value.code == "remove_target_missing"
    assert document["extension-notes"][SLASH_KEY] == {"summary": "keep"}
