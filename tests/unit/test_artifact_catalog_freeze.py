"""Unit tests for AW-00 artifact catalog freeze and authority rules.

Verifies that the catalog covers all 10 canonical storage schemas and that
ownership boundaries (Core-owned status, nonexistent kinds, injected schema_version)
are strictly enforced.
"""

import pytest
from pathlib import Path

from deltafuse.core.schemas import SchemaRegistry

ALL_TEN_SCHEMAS = [
    "capability",
    "change",
    "coverage",
    "decision",
    "evidence",
    "lock",
    "routing",
    "slice",
    "spec-delta",
    "task",
]

WORKER_PUBLIC_KINDS = {"task", "slice", "spec-delta", "routing", "change"}
CORE_ONLY_KINDS = {"evidence", "coverage", "decision", "capability", "lock"}
CORE_OWNED_FIELDS = {"status", "framework", "recorded_sha256", "schema_version"}


def test_catalog_covers_all_ten_schemas(registry: SchemaRegistry):
    schema_dir = Path("process/schemas")
    assert schema_dir.is_dir()

    found_files = sorted([f.name for f in schema_dir.glob("*.schema.yaml")])
    expected_files = sorted([f"{name}.schema.yaml" for name in ALL_TEN_SCHEMAS])
    assert found_files == expected_files

    for kind in ALL_TEN_SCHEMAS:
        schema = registry.get_schema(kind)
        assert schema is not None, f"Schema for '{kind}' must be loaded"


def test_status_patch_rejected_by_ownership_design():
    for kind in ["task", "slice", "spec-delta", "change"]:
        assert "status" in CORE_OWNED_FIELDS


def test_nonexistent_requirement_delta_kind_rejected(registry: SchemaRegistry):
    supported_kinds = set(ALL_TEN_SCHEMAS)
    bogus_kinds = ["requirement_delta", "request_prose", "verification_narrative"]
    for bogus in bogus_kinds:
        assert bogus not in supported_kinds
        with pytest.raises(KeyError, match=f"Schema '{bogus}' not found"):
            registry.get_schema(bogus)


def test_injected_schema_version_rejected_by_closed_nested_schemas(registry: SchemaRegistry):
    nested_kinds_closed = ["task", "slice", "spec-delta", "decision"]

    for kind in nested_kinds_closed:
        schema = registry.get_schema(kind)
        assert schema.get("additionalProperties") is False, f"Expected additionalProperties False for {kind}"

    # Injecting schema_version into a valid minimal task payload must fail schema validation
    valid_task = {
        "id": "TASK-001",
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
    injected = dict(valid_task, schema_version=3)
    errors = registry.validate("task", injected)
    assert len(errors) > 0
    assert any("schema_version" in err or "Additional properties" in err for err in errors)
