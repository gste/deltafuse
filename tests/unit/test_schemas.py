import pytest
from deltafuse.core.schemas import SchemaRegistry, SchemaValidationError

ALL_SCHEMAS = [
    "capability",
    "change",
    "coverage",
    "decision",
    "evidence",
    "routing",
    "slice",
    "spec-delta",
    "task",
]

def test_all_expected_schemas_loaded(registry: SchemaRegistry):
    for schema_name in ALL_SCHEMAS:
        schema = registry.get_schema(schema_name)
        assert schema is not None
        assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
        assert f"https://deltafuse.dev/schemas/v2/{schema_name}.schema.yaml" in schema.get("$id", "")

def test_change_schema_valid_and_invalid(registry: SchemaRegistry):
    valid_change = {
        "schema_version": 2,
        "id": "CHG-042",
        "title": "Fix authentication expiration",
        "status": "normalized",
        "framework": {
            "version": "2.0.0",
            "content_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        },
        "intent": "bugfix",
        "risk": "medium",
        "source": {
            "request": "request.md",
            "intake_refs": []
        },
        "analysis": {
            "routing": "routing.yaml",
            "summary": "analysis.md"
        },
        "deltas": [],
        "slices": [],
        "decisions": [],
        "tasks": [],
        "verification": None
    }
    assert registry.validate("change", valid_change) == []

    # Invalid ID format
    invalid_change = dict(valid_change, id="INVALID-ID")
    errors = registry.validate("change", invalid_change)
    assert any("id" in err for err in errors)

    # additionalProperties false check
    invalid_additional = dict(valid_change, unexpected_key="not_allowed")
    errors = registry.validate("change", invalid_additional)
    assert any("unexpected_key" in err or "Additional properties are not allowed" in err for err in errors)

def test_task_schema_validation(registry: SchemaRegistry):
    valid_task = {
        "id": "TASK-001",
        "change": "CHG-001",
        "slice": "SLICE-01",
        "kind": "feature",
        "status": "pending",
        "depends_on": [],
        "requirement_delta": "added",
        "spec_refs": ["docs/spec/auth.md#REQ-01"],
        "design_ref": None,
        "allowed_paths": ["src/auth.py"],
        "forbidden_paths": ["src/billing.py"],
        "context_budget": {"max_tokens": 16000, "max_files": 24},
    }
    assert registry.validate("task", valid_task) == []

    # Invalid task id pattern (requires 3 digits)
    invalid_task = dict(valid_task, id="TASK-1")
    assert len(registry.validate("task", invalid_task)) > 0

    # Missing required field allowed_paths
    missing_allowed = dict(valid_task)
    del missing_allowed["allowed_paths"]
    assert len(registry.validate("task", missing_allowed)) > 0

    missing_budget = dict(valid_task)
    del missing_budget["context_budget"]
    assert len(registry.validate("task", missing_budget)) > 0

def test_slice_schema_validation(registry: SchemaRegistry):
    valid_slice = {
        "id": "SLICE-01",
        "change": "CHG-001",
        "title": "Session refresh",
        "status": "draft",
        "primary_capability": "identity.session",
        "related_capabilities": [],
        "policies": ["policy.security"],
        "spec_refs": ["docs/spec/session.md"],
        "claims": ["CR-001"],
        "depends_on": [],
        "context_budget": {"max_tokens": 16000, "max_files": 24}
    }
    assert registry.validate("slice", valid_slice) == []

    assert registry.validate("slice", dict(valid_slice, claims=["O1", "E1"])) == []

    # Claim pattern requires CR-001 (3+ digits) or short labels like O1
    invalid_claim_slice = dict(valid_slice, claims=["CR-1"])
    assert len(registry.validate("slice", invalid_claim_slice)) > 0

def test_coverage_schema_validation(registry: SchemaRegistry):
    valid_coverage = {
        "change": "CHG-001",
        "claims": {
            "CR-001": {
                "slice": "SLICE-01",
                "tasks": ["TASK-001"],
                "spec_refs": ["docs/spec/auth.md#REQ-01"],
                "evidence": {
                    "red": "evidence/red/TASK-001.yaml",
                    "green": "evidence/green/TASK-001.yaml",
                    "regression": "evidence/regression/TASK-001.yaml",
                    "verification": "evidence/verification/run.yaml"
                },
                "status": "implemented"
            }
        }
    }
    assert registry.validate("coverage", valid_coverage) == []

def test_evidence_schema_validation(registry: SchemaRegistry):
    valid_evidence = {
        "schema_version": 2,
        "change": "CHG-001",
        "task": "TASK-001",
        "phase": "red",
        "timestamp": "2026-09-04T12:00:00Z",
        "command": "pytest tests/test_auth.py",
        "exit_code": 1,
        "result": "expected-failure",
        "failure_category": "behavioral-mismatch",
        "summary": "Test failed with AssertionError as expected",
        "changed_paths": ["tests/test_auth.py"],
        "spec_status": "unchanged"
    }
    assert registry.validate("evidence", valid_evidence) == []

    already_green = dict(valid_evidence)
    already_green["exit_code"] = 0
    already_green["result"] = "already-green"
    already_green["summary"] = "Public oracle already passes"
    assert registry.validate("evidence", already_green) == []

    # Regression phase requires task
    valid_regression = {
        "schema_version": 2,
        "change": "CHG-001",
        "task": "TASK-001",
        "phase": "regression",
        "timestamp": "2026-09-04T12:00:00Z",
        "command": "pytest tests/",
        "exit_code": 0,
        "result": "passed",
        "summary": "Regression suite passed",
        "changed_paths": ["src/auth.py"],
        "spec_status": "unchanged",
        "base_revision": "sha256:" + ("0" * 64),
    }
    assert registry.validate("evidence", valid_regression) == []

    missing_revision = dict(valid_regression)
    del missing_revision["base_revision"]
    assert len(registry.validate("evidence", missing_revision)) > 0

def test_decision_schema_validation(registry: SchemaRegistry):
    valid_decision = {
        "id": "DEC-0001",
        "title": "Use JWT for session tokens",
        "kind": "architecture",
        "status": "accepted",
        "owner": "lead-arch",
        "date": "2026-09-04",
        "change": "CHG-001",
        "affects": {
            "capabilities": ["identity.auth"],
            "spec_refs": ["docs/spec/auth.md#REQ-01"]
        },
        "supersedes": None,
        "superseded_by": None
    }
    assert registry.validate("decision", valid_decision) == []

def test_capability_schema_validation(registry: SchemaRegistry):
    valid_catalog = {
        "schema_version": 2,
        "domains": {
            "identity": {
                "summary": "User authentication and authorization",
                "responsibility": "Manages credentials and security tokens",
                "capabilities": {
                    "auth": {
                        "summary": "Primary token validation",
                        "responsibility": "Handles login",
                        "type": "business",
                        "status": "active",
                        "excludes": ["Billing"],
                        "actors": ["user"],
                        "entities": ["token"],
                        "events": ["login-attempt"],
                        "spec": ["docs/spec/auth.md"],
                        "policies": ["policy.security"],
                        "code_roots": ["src/auth"],
                        "test_roots": ["tests/auth"],
                        "depends_on": []
                    }
                }
            }
        },
        "policies": {
            "policy.security": {
                "summary": "Security baseline",
                "spec": ["docs/spec/policies/security.md"],
                "applies_to": ["identity.*"]
            }
        }
    }
    assert registry.validate("capability", valid_catalog) == []

def test_routing_schema_validation(registry: SchemaRegistry):
    valid_routing = {
        "change": "CHG-001",
        "claims": {
            "CR-001": {
                "summary": "Allow user login via token",
                "primary_capability": "identity.auth",
                "related_capabilities": ["identity.session"],
                "policies": ["policy.security"],
                "confidence": "high"
            }
        }
    }
    assert registry.validate("routing", valid_routing) == []

def test_spec_delta_schema_validation(registry: SchemaRegistry):
    valid_spec_delta = {
        "change": "CHG-001",
        "status": "proposed",
        "slices": ["SLICE-01"],
        "added": ["docs/spec/auth.md#REQ-02"],
        "modified": [],
        "removed": []
    }
    assert registry.validate("spec-delta", valid_spec_delta) == []

    missing_ops = {
        "change": "CHG-001",
        "status": "proposed",
        "slices": ["SLICE-01"],
    }
    missing_errs = registry.validate("spec-delta", missing_ops)
    assert any("added" in err or "modified" in err or "removed" in err for err in missing_errs)


def test_bootstrap_decision_schema_validation(registry: SchemaRegistry):
    valid_bootstrap = {
        "id": "DEC-0000",
        "title": "Bootstrap Architecture Decision",
        "kind": "architecture",
        "status": "accepted",
        "owner": "lead-arch",
        "date": "2026-09-04",
        "change": None,
        "affects": {
            "capabilities": ["identity.auth"],
            "spec_refs": ["docs/spec/auth.md#REQ-01"],
        },
        "supersedes": None,
        "superseded_by": None,
    }
    assert registry.validate("decision", valid_bootstrap) == []
