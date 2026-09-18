"""Unit tests for Artifact Writer operation and receipt contracts (AW-01).

Validates operation request envelopes, per-kind descriptors, receipt schemas,
and error diagnostic structures.
"""

import json
from pathlib import Path
import pytest
import yaml
from jsonschema import Draft202012Validator


CONTRACTS_DIR = Path("docs/contracts")
OPERATIONS_DIR = Path("process/artifact-operations")

ENVELOPE_SCHEMA_PATH = CONTRACTS_DIR / "artifact-writer.schema.yaml"
RECEIPT_SCHEMA_PATH = OPERATIONS_DIR / "receipt.schema.yaml"
MANIFEST_PATH = OPERATIONS_DIR / "manifest.json"

ALL_KINDS = [
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


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Contract file not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_envelope_schema_exists_and_is_valid():
    assert ENVELOPE_SCHEMA_PATH.is_file(), f"Missing {ENVELOPE_SCHEMA_PATH}"
    schema = load_yaml(ENVELOPE_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "https://deltafuse.dev/contracts/artifact-writer/v1"


def test_receipt_schema_exists_and_is_valid():
    assert RECEIPT_SCHEMA_PATH.is_file(), f"Missing {RECEIPT_SCHEMA_PATH}"
    schema = load_yaml(RECEIPT_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "https://deltafuse.dev/contracts/artifact-writer/receipt/v1"


def test_envelope_validation_valid_and_invalid():
    schema = load_yaml(ENVELOPE_SCHEMA_PATH)
    validator = Draft202012Validator(schema)

    valid_create = {
        "request_id": "req-001",
        "operation": "create",
        "kind": "task",
        "change": "CHG-001",
        "identity": "TASK-001",
        "semantic_payload": {
            "title": "Add auth handler",
            "kind": "feature",
            "allowed_paths": ["src/auth.py"],
        },
    }
    assert list(validator.iter_errors(valid_create)) == []

    # Invalid: unknown top-level field (additionalProperties: false)
    invalid_unknown = dict(valid_create, unexpected_field="bogus")
    errors = list(validator.iter_errors(invalid_unknown))
    assert len(errors) > 0

    # Invalid: missing required field operation
    invalid_missing = dict(valid_create)
    del invalid_missing["operation"]
    assert len(list(validator.iter_errors(invalid_missing))) > 0


def test_patch_structure_validation():
    schema = load_yaml(ENVELOPE_SCHEMA_PATH)
    validator = Draft202012Validator(schema)

    valid_update = {
        "request_id": "req-002",
        "operation": "update",
        "kind": "task",
        "change": "CHG-001",
        "target": "tasks/TASK-001.md",
        "expected_sha256": "sha256:" + ("a" * 64),
        "patch": {
            "set": [{"path": "/title", "value": "Updated Title"}],
            "remove": ["/design_ref"],
            "canonicalize_metadata": False,
        },
    }
    assert list(validator.iter_errors(valid_update)) == []

    # Invalid: set path not starting with /
    invalid_pointer = {
        "request_id": "req-003",
        "operation": "update",
        "kind": "task",
        "change": "CHG-001",
        "target": "tasks/TASK-001.md",
        "patch": {
            "set": [{"path": "title", "value": "Bad Pointer"}],
        },
    }
    errors = list(validator.iter_errors(invalid_pointer))
    assert len(errors) > 0


def test_receipt_validation():
    schema = load_yaml(RECEIPT_SCHEMA_PATH)
    validator = Draft202012Validator(schema)

    valid_receipt = {
        "request_id": "req-001",
        "transaction_id": "tx-100",
        "operation": "create",
        "kind": "task",
        "target": "tasks/TASK-001.md",
        "operation_schema": {
            "version": "1",
            "content_hash": "sha256:" + ("0" * 64),
        },
        "storage_schema": {
            "kind": "task",
            "version": 3,
            "id": "https://deltafuse.dev/schemas/v3/task.schema.yaml",
            "content_hash": "sha256:" + ("0" * 64),
        },
        "serializer_revision": 1,
        "request_sha256": "sha256:" + ("1" * 64),
        "payload_sha256": "sha256:" + ("2" * 64),
        "previous_sha256": None,
        "result_sha256": "sha256:" + ("3" * 64),
        "changed": True,
        "outcome": "committed",
        "timestamp": "2026-09-18T08:00:00Z",
        "authority": {
            "actor": "worker",
            "work_item": "TASK-001",
            "product_root": "c:/repo",
        },
        "validation_scopes": [
            {"scope": "schema", "status": "valid", "details": []}
        ],
        "receipt_sha256": "sha256:" + ("4" * 64),
    }
    assert list(validator.iter_errors(valid_receipt)) == []


def test_descriptors_exist_for_all_ten_kinds():
    assert MANIFEST_PATH.is_file(), f"Missing {MANIFEST_PATH}"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest.get("schema_version") == 1

    descriptors = manifest.get("descriptors", {})
    for kind in ALL_KINDS:
        assert kind in descriptors, f"Missing descriptor entry for {kind} in manifest"
        desc_path = OPERATIONS_DIR / descriptors[kind]["file"]
        assert desc_path.is_file(), f"Descriptor file missing for {kind}: {desc_path}"

        desc = load_yaml(desc_path)
        assert desc["kind"] == kind
        assert desc["operation_version"] == "1"
        assert "allowed_operations" in desc
        assert "core_owned_fields" in desc
