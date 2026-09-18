"""Unit tests for deterministic YAML/frontmatter codec (AW-04)."""

import pytest
from deltafuse.core.artifact_codec import (
    strict_encode_yaml,
    serialize_artifact,
    ArtifactCodecError,
)
from deltafuse.core.artifact_reader import strict_parse_yaml


def test_quoted_scalar_strings_preserved_in_roundtrip():
    data = {
        "yes_str": "yes",
        "no_str": "no",
        "true_str": "true",
        "false_str": "false",
        "date_str": "2026-09-18",
        "zero_str": "01234",
        "null_str": "null",
        "actual_bool": True,
        "actual_null": None,
        "actual_int": 42,
    }
    encoded = strict_encode_yaml(data, kind="task")
    parsed = strict_parse_yaml(encoded)
    assert parsed["yes_str"] == "yes"
    assert parsed["no_str"] == "no"
    assert parsed["true_str"] == "true"
    assert parsed["false_str"] == "false"
    assert parsed["date_str"] == "2026-09-18"
    assert parsed["zero_str"] == "01234"
    assert parsed["null_str"] == "null"
    assert parsed["actual_bool"] is True
    assert parsed["actual_null"] is None
    assert parsed["actual_int"] == 42


def test_canonical_key_ordering():
    data = {
        "context_budget": {"max_tokens": 16000, "max_files": 24},
        "id": "TASK-001",
        "title": "Add auth handler",
        "status": "pending",
        "change": "CHG-001",
        "slice": "SLICE-01",
        "kind": "feature",
    }
    encoded = strict_encode_yaml(data, kind="task")
    lines = [line.split(":")[0].strip() for line in encoded.splitlines() if ":" in line and not line.startswith(" ")]
    assert lines[0] == "id"
    assert lines[1] == "change"
    assert lines[2] == "slice"
    assert lines[3] == "kind"
    assert lines[4] == "status"


def test_multiline_string_formatting():
    data = {"summary": "Line 1\nLine 2\nLine 3\n"}
    encoded = strict_encode_yaml(data, kind="task")
    assert "|" in encoded
    parsed = strict_parse_yaml(encoded)
    assert parsed["summary"] == "Line 1\nLine 2\nLine 3\n"


def test_list_order_preservation():
    data = {"spec_refs": ["REQ-03", "REQ-01", "REQ-02"]}
    encoded = strict_encode_yaml(data, kind="task")
    parsed = strict_parse_yaml(encoded)
    assert parsed["spec_refs"] == ["REQ-03", "REQ-01", "REQ-02"]


def test_body_bytes_and_newlines_preserved():
    meta = {"id": "TASK-001", "change": "CHG-001", "slice": "SLICE-01", "kind": "feature", "status": "pending"}
    body = "## Heading\n\nBody paragraph 1.\n\n\n"
    artifact_str = serialize_artifact(meta, body=body, kind="task")
    assert artifact_str.endswith("## Heading\n\nBody paragraph 1.\n\n\n")


def test_noncanonical_metadata_requires_opt_in():
    existing_raw = """---
# Legacy comment in frontmatter
id: TASK-001
change: CHG-001
slice: SLICE-01
kind: feature
status: pending
---
Body content
"""
    new_meta = {"id": "TASK-001", "change": "CHG-001", "slice": "SLICE-01", "kind": "feature", "status": "pending", "title": "New Title"}

    with pytest.raises(ArtifactCodecError) as exc_info:
        serialize_artifact(
            new_meta,
            body="Body content",
            kind="task",
            existing_raw_content=existing_raw,
            canonicalize_metadata=False,
        )
    assert exc_info.value.code == "format_change_required"
    assert exc_info.value.preview_hash is not None
    assert exc_info.value.preview_hash.startswith("sha256:")


def test_canonicalize_metadata_opt_in_succeeds():
    existing_raw = """---
# Legacy comment in frontmatter
id: TASK-001
change: CHG-001
slice: SLICE-01
kind: feature
status: pending
---
Body content
"""
    new_meta = {"id": "TASK-001", "change": "CHG-001", "slice": "SLICE-01", "kind": "feature", "status": "pending", "title": "New Title"}

    out = serialize_artifact(
        new_meta,
        body="Body content",
        kind="task",
        existing_raw_content=existing_raw,
        canonicalize_metadata=True,
    )
    assert "New Title" in out
    assert out.endswith("Body content")
